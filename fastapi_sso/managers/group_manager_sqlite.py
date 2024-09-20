from datetime import datetime, timedelta, timezone
import secrets
import sqlite3
import uuid
from typing import List, Optional, Dict, Set

from pydantic import TypeAdapter

from fastapi_sso.models.group import GroupBase
from fastapi_sso.models.user import UserBase, UserCreate
from ..utils.utils import generate_deci_code

REFRESH_TOKEN_EXPIRE_DAYS = 30

class GroupManagerSQLite:
    def __init__(self, db_file: str = '../db/user.db'):
        self.db_file = db_file
        
        # Initialize empty caches
        self.groups_cache: Dict[str, GroupBase] = {}  # group_id -> group Model obj
        self.users_cache: Dict[str, UserBase] = {}  # user_id -> user Model obj
        self.user_groups_cache: Dict[str, List[str]] = {}  # user_id -> list of group_ids
        self.group_users_cache: Dict[str, List[str]] = {}  # group_id -> list of user_ids

    # done
    def _get_group_from_db(self, group_id: str) -> Optional[GroupBase]:
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT group_id, group_name FROM groups WHERE group_id = ?', (group_id,))
            result = cursor.fetchone()
            print(result)
            group_dict = dict(result)
            if result:
                group_adapter = TypeAdapter(GroupBase)
                return group_adapter.validate_python(group_dict)
        return None

    # done
    def _get_user_from_db(self, user_id: str) -> Optional[UserBase]:
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           SELECT id, username, email, full_name, bio, profile_picture_url, 
                       status, is_active, is_verified, phone_number, password_hash, 
                       last_seen, created_at, updated_at
                FROM users 
                WHERE id = ?'''
                , (user_id))
            result = cursor.fetchone()
            if result:
                user_dict = dict(result)
                # Convert integer boolean fields to Python booleans
                user_dict['is_active'] = bool(user_dict['is_active'])
                user_dict['is_verified'] = bool(user_dict['is_verified'])
                # Convert string timestamps to datetime objects
                for field in ['last_seen', 'created_at', 'updated_at']:
                    if user_dict[field]:
                        user_dict[field] = datetime.fromisoformat(user_dict[field])
                
                # Use TypeAdapter to validate and create a User instance
                user_adapter = TypeAdapter(UserBase)
                return user_adapter.validate_python(user_dict)
        return None
    # done
    def _get_user_groups_from_db(self, user_id: str) -> List[str]:
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT group_id FROM user_groups WHERE user_id = ?', (user_id,))
            # extracts first column( here it is group_id) from the reulting rows that have been fetched
            return [row[0] for row in cursor.fetchall()]
    # done
    def _get_group_users_from_db(self, group_id: str) -> List[str]:
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM user_groups WHERE group_id = ?', (group_id,))
             # extracts first column ( here it is user_id) from the reulting rows that have been fetched
            return [row[0] for row in cursor.fetchall()]
    # done
    def create_group(self, group_name: str) -> str:
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO groups group_name VALUES (?, ?)', (group_name))
            conn.commit()
        group_id = cursor.lastrowid
        # Update cache
        group = GroupBase(
            group_id=group_id,
            group_name=group_name
        )
        self.groups_cache[group_id] = group
        self.group_users_cache[group_id] = []
        return group

    
    # done
    def create_user(self, user: UserCreate) -> UserBase:
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, full_name, background_information, profile_picture_url, phone_number, auth_provider)
                VALUES (?, ?, ?, ?, ?, ?, ?,?)
            ''', (user.username, user.email, user.password_hash, user.full_name, user.background_information, user.profile_picture_url, user.phone_number,user.auth_provider))
            conn.commit()
        user_id = cursor.lastrowid
        # Update cache
        user = UserBase(
            id=user_id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            background_information=user.background_information,
            profile_picture_url=user.profile_picture_url,
            last_seen=datetime.now().isoformat(),
            phone_number=user.phone_number,
            is_active = True,
            is_verified = False,
            auth_provider=user.auth_provider
        )
        
        self.users_cache[user_id] = user
        self.user_groups_cache[user_id] = []
        
        return user

    # done 
    def add_user_to_group(self, user_id: str, group_id: str) -> bool:
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO user_groups (user_id, group_id) VALUES (?, ?)', (user_id, group_id))
                conn.commit()
            
            # Update cache if the entries exist
            if user_id in self.user_groups_cache:
                self.user_groups_cache[user_id].append(group_id)
            if group_id in self.group_users_cache:
                self.group_users_cache[group_id].append(user_id)
            
            return True
        except sqlite3.IntegrityError:
            return False  # User already in group or user/group doesn't exist
    # done
    def remove_user_from_group(self, user_id: str, group_id: str) -> bool:
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM user_groups WHERE user_id = ? AND group_id = ?', (user_id, group_id))
            conn.commit()
            if cursor.rowcount > 0:
                # Update cache if the entries exist
                if user_id in self.user_groups_cache:
                    self.user_groups_cache[user_id].remove(group_id)
                if group_id in self.group_users_cache:
                    self.group_users_cache[group_id].remove(user_id)
                return True
            return False
    # done
    def get_user_groups(self, user_id: str) -> List[dict]:
        if user_id not in self.user_groups_cache:
            self.user_groups_cache[user_id] = self._get_user_groups_from_db(user_id)
        
        return [self.get_group_by_id(group_id) for group_id in self.user_groups_cache[user_id]]
    # done
    def get_group_users(self, group_id: str) -> List[dict]:
        if group_id not in self.group_users_cache:
            self.group_users_cache[group_id] = self._get_group_users_from_db(group_id)
        
        return [self.get_user_by_id(user_id) for user_id in self.group_users_cache[group_id]]
    # done
    def get_group_by_id(self, group_id: str) -> Optional[dict]:
        if group_id not in self.groups_cache:
            group = self._get_group_from_db(group_id)
            if group:
                self.groups_cache[group_id] = group
            else:
                return None
        return self.groups_cache[group_id]

    # Done
    def get_user_by_id(self, user_id: str) -> Optional[UserBase]:
        if user_id not in self.users_cache:
            user = self._get_user_from_db(user_id)
            if user:
                self.users_cache[user_id] = user
            else:
                return None
        return user
    # Done
    def get_group_by_name(self, group_name: str) -> Optional[GroupBase]:
        # This operation requires a full DB scan if not in cache
        for group in self.groups_cache.values():
            if group['group_name'] == group_name:
                return group
        
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT group_id, group_name FROM groups WHERE group_name = ?', (group_name,))
            result = cursor.fetchone()
            if result:
                group = GroupBase(group_id=result[0],group_name=result[1])
                self.groups_cache[group['group_id']] = group
                return group
        return None
    # done
    def get_user_by_username(self, username: str) -> Optional[UserBase]:
        # This operation requires a full DB scan if not in cache
        for user in self.users_cache.values():
            if user['username'] == username:
                return user
        
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, username, email, full_name, bio, profile_picture_url, 
                       status, is_active, is_verified, phone_number, password_hash, 
                       last_seen, created_at, updated_at
                FROM users 
                WHERE username = ?'''
                , (username))
            result = cursor.fetchone()
            if result:
                user_dict = dict(result)
                # Convert integer boolean fields to Python booleans
                user_dict['is_active'] = bool(user_dict['is_active'])
                user_dict['is_verified'] = bool(user_dict['is_verified'])
                # Convert string timestamps to datetime objects
                for field in ['last_seen', 'created_at', 'updated_at']:
                    if user_dict[field]:
                        user_dict[field] = datetime.fromisoformat(user_dict[field])
                
                # Use TypeAdapter to validate and create a User instance
                user_adapter = TypeAdapter(UserBase)
                return user_adapter.validate_python(user_dict)
            return None
    def get_user_by_email_and_provider(self,email:str,auth_provider:str)-> Optional[UserBase]:
        with sqlite3.connect(self.db_file) as conn:    
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
            SELECT id, username, email, full_name, background_information, profile_picture_url,
                status, is_active, is_verified, phone_number, password_hash,
                last_seen, created_at, updated_at
            FROM users
            WHERE email = ? AND auth_provider = ? ''',
            (email,auth_provider))
            result = cursor.fetchone()
            if result:
                user_dict = dict(result)
                # Convert integer boolean fields to Python booleans
                user_dict['is_active'] = bool(user_dict['is_active'])
                user_dict['is_verified'] = bool(user_dict['is_verified'])
                # Convert string timestamps to datetime objects
                for field in ['last_seen', 'created_at', 'updated_at']:
                    if user_dict[field]:
                        user_dict[field] = datetime.fromisoformat(user_dict[field])
                user_adapter = TypeAdapter(UserBase)
                return user_adapter.validate_python(user_dict)
            return None
                
        
    
    # Done
    def delete_group(self, group_id: str) -> bool:
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM user_groups WHERE group_id = ?', (group_id,))
            cursor.execute('DELETE FROM groups WHERE group_id = ?', (group_id,))
            conn.commit()
            if cursor.rowcount > 0:
                # Update cache
                self.groups_cache.pop(group_id, None)
                self.group_users_cache.pop(group_id, None)
                for user_groups in self.user_groups_cache.values():
                    if group_id in user_groups:
                        user_groups.remove(group_id)
                return True
            return False
    # Done
    def delete_user(self, user_id: str) -> bool:
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM user_groups WHERE user_id = ?', (user_id,))
            cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
            conn.commit()
            if cursor.rowcount > 0:
                # Update cache
                self.users_cache.pop(user_id, None)
                self.user_groups_cache.pop(user_id, None)
                for group_users in self.group_users_cache.values():
                    if user_id in group_users:
                        group_users.remove(user_id)
                return True
            return False
# We need to se if this need to come into play later  
    def get_user_last_seen_online(self, user_id: str) -> str:
            """
            Get the last_seen_online timestamp for a given user_id.
            
            :param user_id: The ID of the user
            :return: The last seen timestamp as a string, or None if user not found
            """
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute('''
                    SELECT last_seen_online 
                    FROM users 
                    WHERE user_id = ?
                    ''', (user_id,))
                    
                    result = cursor.fetchone()
                    if result:
                        return result[0]
                    else:
                        print(f"User with ID {user_id} not found.")
                        return None
                except sqlite3.Error as e:
                    print(f"An error occurred: {e}")
                    return None

    def set_user_last_seen_online(self, user_id: str) -> bool:
            """
            Set the last_seen_online timestamp for a given user_id to the current time.
            
            :param user_id: The ID of the user
            :return: True if successful, False if user not found
            """
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute('''
                    UPDATE users 
                    SET last_seen_online = ? 
                    WHERE user_id = ?
                    ''', (datetime.now().replace(microsecond=0), user_id))
                    
                    if cursor.rowcount == 0:
                        print(f"User with ID {user_id} not found.")
                        return False
                    
                    return True
                except sqlite3.Error as e:
                    print(f"An error occurred: {e}")
                    return False
    
    def get_user_roles(self,user_id:str)->Set[str]:
        with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                try:
                    query = """
                    SELECT DISTINCT r.name AS role_name
                    FROM user_roles ur
                    JOIN roles r ON ur.role_id = r.id
                    WHERE ur.user_id = ?
                    """

                    cursor.execute(query, (user_id,))
                    results = cursor.fetchall()
                    roles = set()
                    for (role,) in results:
                        roles.add(role)
                    return roles
                except sqlite3.Error as e:
                    print(f"An error occurred: {e}")
                    return False
    def create_refresh_token(self,user_id:str)-> Dict:
        refresh_token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
        with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                expires = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
                try:
                    query = """
                        INSERT INTO refresh_tokens (token, user_id, expires) VALUES (?, ?, ?)
                    """
                    cursor = conn.cursor()
                    cursor.execute(query, (refresh_token,user_id,expires))
                    conn.commit()
                    return {'refresh_token':refresh_token,'user_id':user_id,'expires':expires}
                except sqlite3.Error as e:
                    print(f"An error occurred: {e}")
                    return False
    def get_refresh_token(self,token: str)-> Dict:
            with sqlite3.connect(self.db_file) as conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT user_id, expires FROM refresh_tokens WHERE token = ?", (token,))
                    result = cursor.fetchone()
                    if result:
                        user_id, expires_str = result
                        expires = datetime.fromisoformat(expires_str)
                        return {"user_id": user_id, "expires": expires}
                    return None
                except sqlite3.Error as e:
                    print(f"An error occurred: {e}")
                    return False
    def delete_refresh_token(self,token:str):
        with sqlite3.connect(self.db_file) as conn:
                try:
                    cursor = conn.cursor()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM refresh_tokens WHERE token = ?", (token,))
                    conn.commit()
                    return token
                except sqlite3.Error as e:
                    print(f"An error occurred: {e}")
                    return False

