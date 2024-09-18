from typing import List, Optional

from fastapi_sso.models.user import UserBase, UserCreate
from ..managers.group_manager_sqlite import GroupManagerSQLite
class GroupManagementService:
    def __init__(self) -> None:
        self.group_manager = GroupManagerSQLite() # this implementation can be swapped for oother implementations out based on env var, use if statements
        # any other house keeping can be done here too

    def create_group(self, group_name: str) -> str:
        return self.group_manager.create_group(group_name=group_name)

    def create_user(self,user: UserCreate) -> UserBase:
        return self.group_manager.create_user(user)

    def add_user_to_group(self, user_id: str, group_id: str) -> bool:
        return self.group_manager.add_user_to_group(user_id=user_id,group_id=group_id)

    def remove_user_from_group(self, user_id: str, group_id: str) -> bool:
        return self.group_manager.remove_user_from_group(user_id=user_id,group_id=group_id)

    def get_user_groups(self, user_id: str) -> List[dict]:
        return self.group_manager.get_user_groups(user_id)

    def get_group_users(self, group_id: str) -> List[dict]:
        return self.group_manager.get_group_users(group_id)

    def get_group_by_id(self, group_id: str) -> Optional[dict]:
        return self.group_manager.get_group_by_id(group_id)

    def get_user_by_id(self, user_id: str) -> Optional[UserBase]:
        return self.group_manager.get_user_by_id(user_id)

    def get_group_by_name(self, group_name: str) -> Optional[dict]:
        return self.group_manager.get_group_by_name(group_name)
    
    def get_user_by_username(self, username: str) -> Optional[dict]:
        return self.get_user_by_username(username)
    
    def get_user_by_email_and_provider(self,email:str,auth_provider:str) -> Optional[UserBase]:
        return self.group_manager.get_user_by_email_and_provider(email,auth_provider)

    def delete_group(self, group_id: str) -> bool:
        return self.group_manager.delete_group(group_id)

    def delete_user(self, user_id: str) -> bool:
        return self.group_manager.delete_user(user_id)
    
    def set_user_last_seen_online(self,user_id:str)-> bool:
        return self.group_manager.set_user_last_seen_online(user_id)
    
    def get_user_last_seen_online(self,user_id:str)-> bool:
        return self.group_manager.get_user_last_seen_online(user_id)
