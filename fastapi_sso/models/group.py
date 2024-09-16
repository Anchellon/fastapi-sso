from pydantic import BaseModel
from typing import List, Optional

class GroupBase(BaseModel):
    group_name: str

class GroupCreate(GroupBase):
    pass

class GroupInDB(GroupBase):
    id: int

class GroupUpdate(BaseModel):
    group_name: Optional[str] = None

class GroupResponse(GroupInDB):
    pass

class GroupWithUsers(GroupResponse):
    users: List[int]  # List of user IDs

class UserGroup(BaseModel):
    user_id: int
    group_id: int