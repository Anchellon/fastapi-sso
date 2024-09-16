from pydantic import BaseModel, EmailStr, Field, HttpUrl
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    bio: Optional[str] = None
    profile_picture_url: Optional[HttpUrl] = None
    phone_number: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserInDB(UserBase):
    user_id: int
    status: str = Field(default="offline")
    last_seen: datetime = Field(default_factory=datetime.now)
    is_active: bool = True
    is_verified: bool = False
    password_hash: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    bio: Optional[str] = None
    profile_picture_url: Optional[HttpUrl] = None
    phone_number: Optional[str] = None
    status: Optional[str] = None

class UserResponse(UserBase):
    user_id: int
    status: str
    last_seen: datetime
    is_active: bool
    is_verified: bool

    class Config:
        orm_mode = True