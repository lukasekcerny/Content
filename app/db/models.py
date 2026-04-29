from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Platform:
    id: str
    display_name: str
    connected: bool = False
    username: Optional[str] = None
    connected_at: Optional[str] = None


@dataclass
class Content:
    id: Optional[int] = None
    file_path: str = ""
    file_name: str = ""
    mime_type: str = ""
    file_size: int = 0
    width: int = 0
    height: int = 0
    duration_seconds: float = 0.0
    thumbnail_path: str = ""
    title: str = ""
    description: str = ""
    created_at: str = ""


@dataclass
class Post:
    id: Optional[int] = None
    content_id: int = 0
    platform_id: str = ""
    content_type: str = ""
    status: str = "draft"
    caption: str = ""
    title: str = ""
    description: str = ""
    tags: str = ""
    scheduled_at: Optional[str] = None
    published_at: Optional[str] = None
    error_message: Optional[str] = None
    remote_id: Optional[str] = None


@dataclass
class ProfilePicture:
    file_path: Optional[str] = None
    updated_at: Optional[str] = None
