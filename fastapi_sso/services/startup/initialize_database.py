import sqlite3
import os
from typing import List, Tuple

def create_table(cursor: sqlite3.Cursor, table_name: str, columns: List[str]) -> None:
    """Create a table if it doesn't exist."""
    query = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        {', '.join(columns)}
    )
    """
    cursor.execute(query)

def create_index(cursor: sqlite3.Cursor, index_name: str, table_name: str, column: str) -> None:
    """Create an index on a table column if it doesn't exist."""
    query = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column})"
    cursor.execute(query)

def init_sqlite_database(db_file: str) -> None:
    """Initialize the SQLite database with necessary tables and indexes for RBAC."""
    tables = {
        'users': [
            'id INTEGER PRIMARY KEY AUTOINCREMENT',
            'username TEXT UNIQUE',
            'email TEXT NOT NULL ',
            'password_hash TEXT',
            'full_name TEXT',
            'background_information TEXT',
            'goal TEXT',
            'profile_picture_url TEXT',
            'status TEXT NOT NULL DEFAULT "offline"',
            'last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            'created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            'updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            'is_active INTEGER NOT NULL DEFAULT 1',
            'is_verified INTEGER NOT NULL DEFAULT 0',
            'phone_number TEXT',
            'auth_provider TEXT',
            'UNIQUE (email, auth_provider)'

        ],
        'roles': [
            'id INTEGER PRIMARY KEY AUTOINCREMENT',
            'name TEXT NOT NULL UNIQUE',
            'description TEXT'
        ],
        'permissions': [
            'id INTEGER PRIMARY KEY AUTOINCREMENT',
            'name TEXT NOT NULL UNIQUE',
            'description TEXT'
        ],
        'role_permissions': [
            'role_id INTEGER',
            'permission_id INTEGER',
            'FOREIGN KEY (role_id) REFERENCES roles (id)',
            'FOREIGN KEY (permission_id) REFERENCES permissions (id)',
            'PRIMARY KEY (role_id, permission_id)'
        ],
        'user_roles': [
            'user_id INTEGER',
            'role_id INTEGER',
            'FOREIGN KEY (user_id) REFERENCES users (id)',
            'FOREIGN KEY (role_id) REFERENCES roles (id)',
            'PRIMARY KEY (user_id, role_id)'
        ],
        'groups': [
            'group_id INTEGER PRIMARY KEY AUTOINCREMENT',
            'group_name TEXT NOT NULL UNIQUE'
        ],
        'user_groups': [
            'user_id INTEGER NOT NULL,'
            'group_id INTEGER NOT NULL',
            'joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            'role TEXT NOT NULL DEFAULT "member"',
            'PRIMARY KEY (user_id, group_id)',
            'FOREIGN KEY (user_id) REFERENCES users(id)',
            'FOREIGN KEY (group_id) REFERENCES groups(id)'

        ],
        'refresh_tokens':[
            'token TEXT PRIMARY KEY',
            'user_id TEXT NOT NULL',
            'expires TIMESTAMP NOT NULL'
        ]
    }
    
    indexes = [
        ('idx_users_id', 'users', 'id'),
        ('idx_users_email', 'users', 'email'),
        ('idx_users_username', 'users', 'username'),
        ('idx_roles_name', 'roles', 'name'),
        ('idx_permissions_name', 'permissions', 'name'),
        ('idx_role_permissions_role_id', 'role_permissions', 'role_id'),
        ('idx_role_permissions_permission_id', 'role_permissions', 'permission_id'),
        ('idx_user_roles_user_id', 'user_roles', 'user_id'),
        ('idx_user_roles_role_id', 'user_roles', 'role_id'),
        ('idx_user_groups_user_id', 'user_groups', 'user_id'),
        ('idx_user_groups_group_id', 'user_groups', 'group_id'),
        ('idx_groups_name', 'groups','group_name')
    ]

    try:
        with sqlite3.connect(db_file) as conn:
            cursor = conn.cursor()
            
            for table_name, columns in tables.items():
                create_table(cursor, table_name, columns)
            
            for index_name, table_name, column in indexes:
                create_index(cursor, index_name, table_name, column)
            
            conn.commit()
    except sqlite3.Error as e:
        print(f"An error occurred while initializing the database: {e}")

def ensure_file_exists(file_path: str) -> bool:
    """
    Check if a file exists, and create it if it doesn't.
    
    Args:
    file_path (str): The path to the file to check/create.
    
    Returns:
    bool: True if the file already existed, False if it was created.
    """
    if os.path.exists(file_path):
        return True
    else:
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            open(file_path, 'a').close()
            return False
        except Exception as e:
            print(f"Error creating file {file_path}: {e}")
            return False

def insert_roles(db_file: str) -> None:
    """Insert predefined roles into the roles table."""
    roles = [
        ('USER', 'A person who uses the app'),
        ('ADMIN', 'Has all permissions')
    ]

    try:
        with sqlite3.connect(db_file) as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT OR IGNORE INTO roles (name, description)
                VALUES (?, ?)
            """, roles)
            conn.commit()
            print(f"Successfully inserted or updated {len(roles)} roles.")
    except sqlite3.Error as e:
        print(f"An error occurred while inserting roles: {e}")
# Example usage
if __name__ == "__main__":
    db_file = "path/to/your/database.db"
    if ensure_file_exists(db_file):
        print("Database file already exists.")
    else:
        print("Created new database file.")
    
    init_sqlite_database(db_file)
    print("Database initialized successfully.")