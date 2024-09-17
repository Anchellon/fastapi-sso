from pydantic import BaseModel
from typing import List, Optional

class GroupBase(BaseModel):
    group_id: int
    group_name: str

class GroupCreate(GroupBase):
    pass



class GroupUpdate(BaseModel):
    group_name: Optional[str] = None


class GroupWithUsers(GroupResponse):
    users: List[int]  # List of user IDs

class UserGroup(BaseModel):
    user_id: int
    