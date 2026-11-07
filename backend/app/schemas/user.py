from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class UserProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phone: str | None = None
    address: str | None = None
    preferred_style: str | None = None
    preferred_colors: str | None = None
    preferred_materials: str | None = None
    created_at: datetime
    updated_at: datetime


class UserProfileUpdate(BaseModel):
    phone: str | None = Field(None, max_length=30)
    address: str | None = Field(None, max_length=500)
    preferred_style: str | None = Field(None, max_length=100)
    preferred_colors: str | None = Field(None, max_length=255)
    preferred_materials: str | None = Field(None, max_length=255)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    is_active: bool
    role: RoleRead
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=255)

