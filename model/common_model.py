from dataclasses import dataclass, field
from typing import Optional, List, Any

from nonebot.adapters.onebot.v11 import MessageSegment, Message


@dataclass
class Status:
    is_success: bool
    message: Any


@dataclass
class RateLimitStatus:
    is_limited: bool
    prompt: Optional[str]


@dataclass
class ValidatedTimestampStatus(Status):
    validated_timestamp: str = ''


@dataclass
class TwitchDownloadStatus(Status):
    file_path: str = ''


@dataclass
class DiscordMessageStatus(Status):
    message: List[MessageSegment] = field(default_factory=lambda: [])
    group_to_notify: str = ''
    has_update: bool = False
    is_edit: bool = False


@dataclass
class DiscordGroupNotification(Status):
    message: Message
    has_update: bool
    group_to_notify: str
    channel_name: str
    channel_id: str
    is_edit: bool
