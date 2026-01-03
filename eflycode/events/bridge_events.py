from __future__ import annotations

from enum import StrEnum
from typing import Any, Callable, Dict, List, Mapping, Type
from uuid import uuid4

from pydantic import Field

from eflycode.events.base import BaseEventPayload
from eflycode.events.ui_events import (
    UIEventType,
    DisplayMessagePayload,
    ProgressPayload,
    create_ui_event_data,
)
from eflycode.events.worker_events import WorkerEventType, create_worker_event_data


class BridgeEventType(StrEnum):
    """
    中介事件类型
    """

    BRIDGE_INIT = "bridge.init"
    UI_TO_WORKER_FORWARD = "bridge.ui_to_worker.forward"
    WORKER_TO_UI_FORWARD = "bridge.worker_to_ui.forward"
    BRIDGE_ERROR = "bridge.error"


class BridgePayload(BaseEventPayload):
    """
    通用中介载荷
    """

    source_event: str
    target_event: str
    description: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BridgeInitPayload(BaseEventPayload):
    """
    中介初始化载荷
    """

    ui_channel_config: Dict[str, Any] = Field(default_factory=dict)
    worker_channel_config: Dict[str, Any] = Field(default_factory=dict)


class BridgeErrorPayload(BaseEventPayload):
    """
    中介错误载荷
    """

    error: str
    details: Dict[str, Any] = Field(default_factory=dict)


BridgePayloadType = Type[BaseEventPayload]

BRIDGE_EVENT_PAYLOADS: Dict[BridgeEventType, BridgePayloadType] = {
    BridgeEventType.BRIDGE_INIT: BridgeInitPayload,
    BridgeEventType.BRIDGE_ERROR: BridgeErrorPayload,
    BridgeEventType.UI_TO_WORKER_FORWARD: BridgePayload,
    BridgeEventType.WORKER_TO_UI_FORWARD: BridgePayload,
}


def create_bridge_event_data(event: BridgeEventType, **kwargs) -> BaseEventPayload:
    """
    创建Bridge事件载荷
    """

    payload_cls = BRIDGE_EVENT_PAYLOADS.get(event, BridgePayload)
    return payload_cls(**kwargs)


WorkerToUIRule = Callable[[Mapping[str, Any]], List[Dict[str, Any]]]
UIToWorkerRule = Callable[[Mapping[str, Any]], List[Dict[str, Any]]]


def _worker_task_start_to_ui(data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    task_id = data.get("task_id", str(uuid4()))
    task_type = data.get("task_type", "task_review")
    payload = create_ui_event_data(
        UIEventType.DISPLAY_INFO,
        message=f"[task_review] {task_id} => {task_type}",
        level="info",
    )
    return [{"event": UIEventType.DISPLAY_INFO.value, **payload.to_dict()}]


def _worker_task_progress_to_ui(data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    payload = ProgressPayload(
        description=data.get("message", "processing"),
        current=data.get("current", 0),
        total=data.get("total"),
    )
    return [{"event": UIEventType.SHOW_LOADING.value, **payload.to_dict()}]


def _worker_task_complete_to_ui(data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    status = data.get("status", "success")
    payload = create_ui_event_data(
        UIEventType.DISPLAY_INFO if status == "success" else UIEventType.DISPLAY_ERROR,
        message=f"任务完成: {status}",
        level="info" if status == "success" else "error",
    )
    event_value = UIEventType.DISPLAY_INFO.value if status == "success" else UIEventType.DISPLAY_ERROR.value
    return [{"event": event_value, **payload.to_dict()}]


def _worker_message_to_ui(data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    payload = create_ui_event_data(
        UIEventType.DISPLAY_INFO,
        message=data.get("message", ""),
        level="info",
    )
    return [{"event": UIEventType.DISPLAY_INFO.value, **payload.to_dict()}]


WORKER_TO_UI_RULES: Dict[WorkerEventType, WorkerToUIRule] = {
    WorkerEventType.TASK_START: _worker_task_start_to_ui,
    WorkerEventType.TASK_PROGRESS: _worker_task_progress_to_ui,
    WorkerEventType.TASK_COMPLETE: _worker_task_complete_to_ui,
    WorkerEventType.TASK_ERROR: _worker_task_complete_to_ui,
    WorkerEventType.MESSAGE_SEND: _worker_message_to_ui,
    WorkerEventType.REASONING_UPDATE: _worker_message_to_ui,
}


def convert_worker_event_to_ui_events(event: str, data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """
    将Worker事件转换为UI事件
    """

    try:
        worker_event = WorkerEventType(event)
    except ValueError:
        return []

    builder = WORKER_TO_UI_RULES.get(worker_event)
    if not builder:
        return []
    return builder(data)


def _ui_user_input_to_worker(data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    payload = create_worker_event_data(
        WorkerEventType.TASK_START,
        task_id=data.get("request_id", str(uuid4())),
        task_type="user_input",
        input_data={"text": data.get("text", "")},
        priority=1,
    )
    return [{"event": WorkerEventType.TASK_START.value, **payload.to_dict()}]


def _ui_info_to_worker(data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    payload = create_worker_event_data(
        WorkerEventType.MESSAGE_RECEIVE,
        task_id=data.get("task_id", str(uuid4())),
        message=data.get("message", ""),
    )
    return [{"event": WorkerEventType.MESSAGE_RECEIVE.value, **payload.to_dict()}]


UI_TO_WORKER_RULES: Dict[UIEventType, UIToWorkerRule] = {
    UIEventType.USER_INPUT_RECEIVED: _ui_user_input_to_worker,
    UIEventType.DISPLAY_INFO: _ui_info_to_worker,
}


def convert_ui_event_to_worker_events(event: str, data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """
    将UI事件转换为Worker事件
    """

    try:
        ui_event = UIEventType(event)
    except ValueError:
        return []

    builder = UI_TO_WORKER_RULES.get(ui_event)
    if not builder:
        return []
    return builder(data)


__all__ = [
    "BridgeEventType",
    "BridgePayload",
    "BridgeInitPayload",
    "BridgeErrorPayload",
    "create_bridge_event_data",
    "convert_worker_event_to_ui_events",
    "convert_ui_event_to_worker_events",
]

