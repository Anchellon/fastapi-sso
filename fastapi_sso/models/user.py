from pydantic import BaseModel, Field, EmailStr
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    id: int
    username: str = Field(..., min_length=1, max_length=50)
    email: EmailStr
    full_name: str
    bio: Optional[str] = None
    profile_picture_url: Optional[str] = None
    status: str = "offline"
    is_active: bool = True
    is_verified: bool = False
    phone_number: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=1, max_length=50)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    bio: Optional[str] = None
    profile_picture_url: Optional[str] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    phone_number: Optional[str] = None

class UserInDB(UserBase):
    password_hash: str
    last_seen: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class User(UserInDB):
    pass