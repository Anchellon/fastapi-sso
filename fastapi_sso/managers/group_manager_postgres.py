import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime, timedelta, timezone
import secrets
import uuid
from typing import List, Optional, Dict, Set

from pydantic import TypeAdapter

from fastapi_sso.models.group import GroupBase
from fastapi_sso.models.user import UserBase, UserCreate
from ..utils.utils import generate_deci_code

REFRESH_TOKEN_EXPIRE_DAYS = 30

class GroupManagerPostgres:
    def __init__(self, db_params: Dict[str, str]):
        self.db_params = db_params
        
        # Initialize empty caches
        self.groups_cache: Dict[str, GroupBase] = {}
        self.users_cache: Dict[str, UserBase] = {}
        self.user_groups_cache: Dict[str, List[str]] = {}
        self.group_users_cache: Dict[str, List[str]] = {}

    def get_connection(self):
        return psycopg2.connect(**self.db_params)

    def _get_group_from_db(self, group_id: str) -> Optional[GroupBase]:
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute('SELECT group_id, group_name FROM groups WHERE group_id = %s', (group_id,))
                result = cursor.fetchone()
                if result:
                    group_dict = dict(result)
                    group_adapter = TypeAdapter(GroupBase)
                    return group_adapter.validate_python(group_dict)
        return None

    def _get_user_from_db(self, user_id: str) -> Optional[UserBase]:
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute('''
                    SELECT id, username, email, full_name, background_information, profile_picture_url, 
                           status, is_active, is_verified, phone_number, password_hash, 
                           last_seen, created_at, updated_at
                    FROM users 
                    WHERE id = %s''', (user_id,))
                result = cursor.fetchone()
                if result:
                    user_dict = dict(result)
                    user_dict['is_active'] = bool(user_dict['is_active'])
                    user_dict['is_verified'] = bool(user_dict['is_verified'])
                    for field in ['last_seen', 'created_at', 'updated_at']:
                        if user_dict[field]:
                            user_dict[field] = user_dict[field].replace(tzinfo=timezone.utc)
                    
                    user_adapter = TypeAdapter(UserBase)
                    return user_adapter.validate_python(user_dict)
        return None

    def _get_user_groups_from_db(self, user_id: str) -> List[str]:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT group_id FROM user_groups WHERE user_id = %s', (user_id,))
                return [row[0] for row in cursor.fetchall()]

    def _get_group_users_from_db(self, group_id: str) -> List[str]:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT user_id FROM user_groups WHERE group_id = %s', (group_id,))
                return [row[0] for row in cursor.fetchall()]
    def create_group(self, group_name: str) -> str:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('INSERT INTO groups (group_name) VALUES (%s) RETURNING group_id', (group_name,))
                group_id = cursor.fetchone()[0]
                conn.commit()

        group = GroupBase(group_id=group_id, group_name=group_name)
        self.groups_cache[group_id] = group
        self.group_users_cache[group_id] = []
        return group

    def create_user(self, user: UserCreate) -> UserBase:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO users (username, email, password_hash, full_name, background_information, 
                                       profile_picture_url, phone_number, auth_provider)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                ''', (user.username, user.email, user.password_hash, user.full_name, 
                      user.background_information, user.profile_picture_url, user.phone_number, 
                      user.auth_provider))
                user_id = cursor.fetchone()[0]
                conn.commit()

        user = UserBase(
            id=user_id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            background_information=user.background_information,
            profile_picture_url=user.profile_picture_url,
            last_seen=datetime.now(timezone.utc),
            phone_number=user.phone_number,
            is_active=True,
            is_verified=False,
            auth_provider=user.auth_provider
        )
        
        self.users_cache[user_id] = user
        self.user_groups_cache[user_id] = []
        
        return user

    def add_user_to_group(self, user_id: str, group_id: str) -> bool:
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('INSERT INTO user_groups (user_id, group_id) VALUES (%s, %s)', 
                                   (user_id, group_id))
                    conn.commit()
            
            if user_id in self.user_groups_cache:
                self.user_groups_cache[user_id].append(group_id)
            if group_id in self.group_users_cache:
                self.group_users_cache[group_id].append(user_id)
            
            return True
        except psycopg2.IntegrityError:
            return False

    def remove_user_from_group(self, user_id: str, group_id: str) -> bool:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('DELETE FROM user_groups WHERE user_id = %s AND group_id = %s', 
                               (user_id, group_id))
                affected_rows = cursor.rowcount
                conn.commit()

        if affected_rows > 0:
            if user_id in self.user_groups_cache:
                self.user_groups_cache[user_id].remove(group_id)
            if group_id in self.group_users_cache:
                self.group_users_cache[group_id].remove(user_id)
            return True
        return False

    def get_user_groups(self, user_id: str) -> List[dict]:
        if user_id not in self.user_groups_cache:
            self.user_groups_cache[user_id] = self._get_user_groups_from_db(user_id)
        
        return [self.get_group_by_id(group_id) for group_id in self.user_groups_cache[user_id]]

    def get_group_users(self, group_id: str) -> List[dict]:
        if group_id not in self.group_users_cache:
            self.group_users_cache[group_id] = self._get_group_users_from_db(group_id)
        
        return [self.get_user_by_id(user_id) for user_id in self.group_users_cache[group_id]]

    def get_group_by_id(self, group_id: str) -> Optional[dict]:
        if group_id not in self.groups_cache:
            group = self._get_group_from_db(group_id)
            if group:
                self.groups_cache[group_id] = group
            else:
                return None
        return self.groups_cache[group_id]

    def get_user_by_id(self, user_id: str) -> Optional[UserBase]:
        if user_id not in self.users_cache:
            user = self._get_user_from_db(user_id)
            if user:
                self.users_cache[user_id] = user
            else:
                return None
        return self.users_cache[user_id]

    def get_group_by_name(self, group_name: str) -> Optional[GroupBase]:
        for group in self.groups_cache.values():
            if group.group_name == group_name:
                return group
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute('SELECT group_id, group_name FROM groups WHERE group_name = %s', (group_name,))
                result = cursor.fetchone()
                if result:
                    group = GroupBase(group_id=result['group_id'], group_name=result['group_name'])
                    self.groups_cache[group.group_id] = group
                    return group
        return None

    def get_user_by_username(self, username: str) -> Optional[UserBase]:
        for user in self.users_cache.values():
            if user.username == username:
                return user
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute('''
                    SELECT id, username, email, full_name, background_information, profile_picture_url, 
                           status, is_active, is_verified, phone_number, password_hash, 
                           last_seen, created_at, updated_at
                    FROM users 
                    WHERE username = %s''', (username,))
                result = cursor.fetchone()
                if result:
                    user_dict = dict(result)
                    user_dict['is_active'] = bool(user_dict['is_active'])
                    user_dict['is_verified'] = bool(user_dict['is_verified'])
                    for field in ['last_seen', 'created_at', 'updated_at']:
                        if user_dict[field]:
                            user_dict[field] = user_dict[field].replace(tzinfo=timezone.utc)
                    
                    user_adapter = TypeAdapter(UserBase)
                    return user_adapter.validate_python(user_dict)
        return None

    def get_user_by_email_and_provider(self, email: str, auth_provider: str) -> Optional[UserBase]:
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute('''
                    SELECT id, username, email, full_name, background_information, profile_picture_url,
                           status, is_active, is_verified, phone_number, password_hash,
                           last_seen, created_at, updated_at
                    FROM users
                    WHERE email = %s AND auth_provider = %s''', (email, auth_provider))
                result = cursor.fetchone()
                if result:
                    user_dict = dict(result)
                    user_dict['is_active'] = bool(user_dict['is_active'])
                    user_dict['is_verified'] = bool(user_dict['is_verified'])
                    for field in ['last_seen', 'created_at', 'updated_at']:
                        if user_dict[field]:
                            user_dict[field] = user_dict[field].replace(tzinfo=timezone.utc)
                    user_adapter = TypeAdapter(UserBase)
                    return user_adapter.validate_python(user_dict)
        return None

    def delete_group(self, group_id: str) -> bool:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('DELETE FROM user_groups WHERE group_id = %s', (group_id,))
                cursor.execute('DELETE FROM groups WHERE group_id = %s', (group_id,))
                affected_rows = cursor.rowcount
                conn.commit()

        if affected_rows > 0:
            self.groups_cache.pop(group_id, None)
            self.group_users_cache.pop(group_id, None)
            for user_groups in self.user_groups_cache.values():
                if group_id in user_groups:
                    user_groups.remove(group_id)
            return True
        return False

    def delete_user(self, user_id: str) -> bool:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('DELETE FROM user_groups WHERE user_id = %s', (user_id,))
                cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
                affected_rows = cursor.rowcount
                conn.commit()

        if affected_rows > 0:
            self.users_cache.pop(user_id, None)
            self.user_groups_cache.pop(user_id, None)
            for group_users in self.group_users_cache.values():
                if user_id in group_users:
                    group_users.remove(user_id)
            return True
        return False

    def get_user_last_seen_online(self, user_id: str) -> str:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute('''
                    SELECT last_seen_online 
                    FROM users 
                    WHERE id = %s
                    ''', (user_id,))
                    
                    result = cursor.fetchone()
                    if result:
                        return result[0].isoformat()
                    else:
                        print(f"User with ID {user_id} not found.")
                        return None
                except psycopg2.Error as e:
                    print(f"An error occurred: {e}")
                    return None

    def set_user_last_seen_online(self, user_id: str) -> bool:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute('''
                    UPDATE users 
                    SET last_seen_online = %s 
                    WHERE id = %s
                    ''', (datetime.now(timezone.utc).replace(microsecond=0), user_id))
                    
                    affected_rows = cursor.rowcount
                    conn.commit()
                    
                    if affected_rows == 0:
                        print(f"User with ID {user_id} not found.")
                        return False
                    
                    return True
                except psycopg2.Error as e:
                    print(f"An error occurred: {e}")
                    return False
    def get_user_roles(self, user_id: str) -> Set[str]:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    query = """
                    SELECT DISTINCT r.name AS role_name
                    FROM user_roles ur
                    JOIN roles r ON ur.role_id = r.id
                    WHERE ur.user_id = %s
                    """

                    cursor.execute(query, (user_id,))
                    results = cursor.fetchall()
                    roles = set(role[0] for role in results)
                    return roles
                except psycopg2.Error as e:
                    print(f"An error occurred: {e}")
                    return set()

    def create_refresh_token(self, user_id: str) -> Dict:
        refresh_token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    query = """
                        INSERT INTO refresh_tokens (token, user_id, expires) 
                        VALUES (%s, %s, %s)
                    """
                    cursor.execute(query, (refresh_token, user_id, expires))
                    conn.commit()
                    return {'refresh_token': refresh_token, 'user_id': user_id, 'expires': expires}
                except psycopg2.Error as e:
                    print(f"An error occurred: {e}")
                    return None

    def get_refresh_token(self, token: str) -> Dict:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute("SELECT user_id, expires FROM refresh_tokens WHERE token = %s", (token,))
                    result = cursor.fetchone()
                    if result:
                        user_id, expires = result
                        return {"user_id": user_id, "expires": expires}
                    return None
                except psycopg2.Error as e:
                    print(f"An error occurred: {e}")
                    return None

    def delete_refresh_token(self, token: str):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute("DELETE FROM refresh_tokens WHERE token = %s", (token,))
                    conn.commit()
                    return token
                except psycopg2.Error as e:
                    print(f"An error occurred: {e}")
                    return None

    def assign_roles(self, user_id, roles):
        with self.get_connection() as conn:
            try:
                with conn.cursor() as cursor:
                    # Start a transaction
                    conn.autocommit = False

                    # Get current roles for the user
                    cursor.execute("""
                        SELECT r.name 
                        FROM user_roles ur 
                        JOIN roles r ON ur.role_id = r.id 
                        WHERE ur.user_id = %s
                    """, (user_id,))
                    current_roles = set(role[0] for role in cursor.fetchall())

                    # Determine roles to add and remove
                    new_roles = set(roles)
                    roles_to_add = new_roles - current_roles
                    roles_to_remove = current_roles - new_roles

                    # Add new roles
                    for role in roles_to_add:
                        cursor.execute("SELECT id FROM roles WHERE name = %s", (role,))
                        result = cursor.fetchone()
                        if result:
                            role_id = result[0]
                            cursor.execute("""
                                INSERT INTO user_roles (user_id, role_id) 
                                VALUES (%s, %s)
                                ON CONFLICT (user_id, role_id) DO NOTHING
                            """, (user_id, role_id))
                        else:
                            print(f"Warning: Role '{role}' not found in the database.")

                    # Remove roles
                    for role in roles_to_remove:
                        cursor.execute("""
                            DELETE FROM user_roles
                            WHERE user_id = %s AND role_id = (SELECT id FROM roles WHERE name = %s)
                        """, (user_id, role))

                    # Commit the transaction
                    conn.commit()
                    print(f"Successfully updated roles for user {user_id}")

            except psycopg2.Error as e:
                # If there's an error, roll back the changes
                conn.rollback()
                print(f"An error occurred: {e}")
            finally:
                conn.autocommit = True

    def get_roles(self, user_id):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    # Query to get user roles
                    cursor.execute("""
                        SELECT r.name 
                        FROM user_roles ur
                        JOIN roles r ON ur.role_id = r.id
                        WHERE ur.user_id = %s
                    """, (user_id,))
                    
                    # Fetch all roles
                    roles = [role[0] for role in cursor.fetchall()]
                    
                    return roles

                except psycopg2.Error as e:
                    print(f"An error occurred: {e}")
                    return []