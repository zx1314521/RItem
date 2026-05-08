from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    image_url: Optional[str] = None
    thread_id: str = Field(min_length=1, max_length=128)


class ChatThreadCreate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=80)


class ChatThreadResponse(BaseModel):
    thread_id: str
    title: str
    created_at: str
    updated_at: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=128)
    phone: Optional[str] = Field(default=None, min_length=5, max_length=20)


class LoginRequest(BaseModel):
    account: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=6, max_length=128)


class UserResponse(BaseModel):
    id: int
    username: str
    phone: Optional[str] = None
    created_at: str
    updated_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_at: str
    user: UserResponse


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=6, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


class SettingsUpdate(BaseModel):
    mcp_enabled: Optional[bool] = None
    mcp_read_enabled: Optional[bool] = None
    mcp_write_enabled: Optional[bool] = None


class SettingsResponse(BaseModel):
    user_id: int
    mcp_enabled: bool
    mcp_read_enabled: bool
    mcp_write_enabled: bool
    mcp_base_url: str
    mcp_server_command: str
    mcp_server_args: list[str]
    mcp_client_config: dict[str, Any]
    mcp_note: str
    updated_at: str


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=2000)
    image_url: Optional[str] = Field(default=None, max_length=2048)


class ItemUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=2000)
    image_url: Optional[str] = Field(default=None, max_length=2048)


class ItemResponse(BaseModel):
    id: int
    user_id: int
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    created_at: str
    updated_at: str
