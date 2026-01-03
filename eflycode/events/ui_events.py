from __future__ import annotations

from enum import StrEnum
from typing import Dict, List, Literal, Type

from pydantic import Field

from eflycode.events.base import BaseEventPayload


class UIEventType(StrEnum):
    """
    UI事件类型
    """

    START_APP = "start_app"
    STOP_APP = "stop_app"
    QUIT_UI = "quit_ui"
    SHOW_WELCOME = "show_welcome"
    SHOW_HELP = "show_help"
    CLEAR_SCREEN = "clear_screen"
    DISPLAY_INFO = "info"
    DISPLAY_WARNING = "warning"
    DISPLAY_ERROR = "error"
    SHOW_LOADING = "progress_start"
    UPDATE_LOADING = "progress_update"
    HIDE_LOADING = "progress_end"
    FILE_OPEN = "file_open"
    FILE_UPDATE = "file_update"
    USER_INPUT_REQUESTED = "user_input"
    USER_INPUT_RECEIVED = "user_input_received"
    USER_CONFIRMED = "user_confirm"
    UI_READY = "ui.ready"
    UI_BUSY = "ui.busy"
    UI_IDLE = "ui.idle"


class WelcomePayload(BaseEventPayload):
    """
    欢迎信息载荷
    """

    title: str = "Welcome"
    features: List[str] = Field(default_factory=list)


class DisplayMessagePayload(BaseEventPayload):
    """
    通用消息载荷
    """

    message: str
    level: Literal["info", "warning", "error"] = "info"


class ProgressPayload(BaseEventPayload):
    """
    进度载荷
    """

    description: str
    current: int = 0
    total: int | None = None


class UserInputPayload(BaseEventPayload):
    """
    用户输入载荷
    """

    text: str
    input_type: Literal["text", "command", "code"] = "text"


class ConfirmationPayload(BaseEventPayload):
    """
    用户确认载荷
    """

    prompt: str
    accepted: bool | None = None


class UIStatePayload(BaseEventPayload):
    """
    UI状态载荷
    """

    state: Literal["ready", "busy", "idle"]


UI_EVENT_PAYLOADS: Dict[UIEventType, Type[BaseEventPayload]] = {
    UIEventType.SHOW_WELCOME: WelcomePayload,
    UIEventType.SHOW_HELP: DisplayMessagePayload,
    UIEventType.DISPLAY_INFO: DisplayMessagePayload,
    UIEventType.DISPLAY_WARNING: DisplayMessagePayload,
    UIEventType.DISPLAY_ERROR: DisplayMessagePayload,
    UIEventType.SHOW_LOADING: ProgressPayload,
    UIEventType.UPDATE_LOADING: ProgressPayload,
    UIEventType.HIDE_LOADING: ProgressPayload,
    UIEventType.FILE_OPEN: DisplayMessagePayload,
    UIEventType.FILE_UPDATE: DisplayMessagePayload,
    UIEventType.USER_INPUT_RECEIVED: UserInputPayload,
    UIEventType.USER_INPUT_REQUESTED: DisplayMessagePayload,
    UIEventType.USER_CONFIRMED: ConfirmationPayload,
    UIEventType.UI_READY: UIStatePayload,
    UIEventType.UI_BUSY: UIStatePayload,
    UIEventType.UI_IDLE: UIStatePayload,
}


def create_ui_event_data(event: UIEventType, **kwargs) -> BaseEventPayload:
    """
    创建UI事件载荷
    """

    payload_cls = UI_EVENT_PAYLOADS.get(event, DisplayMessagePayload)
    return payload_cls(**kwargs)


__all__ = [
    "UIEventType",
    "WelcomePayload",
    "DisplayMessagePayload",
    "ProgressPayload",
    "UserInputPayload",
    "ConfirmationPayload",
    "UIStatePayload",
    "create_ui_event_data",
]

