from __future__ import annotations

from enum import StrEnum
from typing import Any, Dict, Literal, Type
from uuid import uuid4

from pydantic import Field

from eflycode.events.base import BaseEventPayload


class WorkerEventType(StrEnum):
    """
    Worker事件类型
    """

    WORKER_INIT = "worker.init"
    TASK_START = "worker.task_start"
    TASK_PROGRESS = "worker.task_progress"
    TASK_COMPLETE = "worker.task_complete"
    TASK_ERROR = "worker.task_error"
    REASONING_START = "think_start"
    REASONING_UPDATE = "think_update"
    REASONING_END = "think_end"
    TOOL_CALL_REQUEST = "tool_call_start"
    TOOL_CALL_EXECUTE = "tool_call_end"
    TOOL_CALL_SUCCESS = "tool_call_finish"
    TOOL_CALL_ERROR = "tool_call_error"
    MESSAGE_RECEIVE = "message_start"
    MESSAGE_SEND = "message_update"


class TaskStartPayload(BaseEventPayload):
    """
    任务开始载荷
    """

    task_id: str = Field(default_factory=lambda: str(uuid4()))
    task_type: str
    input_data: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 0


class TaskProgressPayload(BaseEventPayload):
    """
    任务进度载荷
    """

    task_id: str
    current: int
    total: int | None = None
    message: str | None = None


class TaskResultPayload(BaseEventPayload):
    """
    任务结果载荷
    """

    task_id: str
    status: Literal["success", "failed"]
    output_data: Dict[str, Any] = Field(default_factory=dict)


class ReasoningPayload(BaseEventPayload):
    """
    推理过程载荷
    """

    task_id: str
    content: str


class ToolCallPayload(BaseEventPayload):
    """
    工具调用载荷
    """

    task_id: str
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class WorkerMessagePayload(BaseEventPayload):
    """
    Worker消息载荷
    """

    task_id: str
    message: str


WORKER_EVENT_PAYLOADS: Dict[WorkerEventType, Type[BaseEventPayload]] = {
    WorkerEventType.TASK_START: TaskStartPayload,
    WorkerEventType.TASK_PROGRESS: TaskProgressPayload,
    WorkerEventType.TASK_COMPLETE: TaskResultPayload,
    WorkerEventType.TASK_ERROR: TaskResultPayload,
    WorkerEventType.REASONING_START: ReasoningPayload,
    WorkerEventType.REASONING_UPDATE: ReasoningPayload,
    WorkerEventType.REASONING_END: ReasoningPayload,
    WorkerEventType.TOOL_CALL_REQUEST: ToolCallPayload,
    WorkerEventType.TOOL_CALL_EXECUTE: ToolCallPayload,
    WorkerEventType.TOOL_CALL_SUCCESS: ToolCallPayload,
    WorkerEventType.TOOL_CALL_ERROR: ToolCallPayload,
    WorkerEventType.MESSAGE_RECEIVE: WorkerMessagePayload,
    WorkerEventType.MESSAGE_SEND: WorkerMessagePayload,
}


def create_worker_event_data(event: WorkerEventType, **kwargs) -> BaseEventPayload:
    """
    创建Worker事件载荷
    """

    payload_cls = WORKER_EVENT_PAYLOADS.get(event, WorkerMessagePayload)
    return payload_cls(**kwargs)


__all__ = [
    "WorkerEventType",
    "TaskStartPayload",
    "TaskProgressPayload",
    "TaskResultPayload",
    "ReasoningPayload",
    "ToolCallPayload",
    "WorkerMessagePayload",
    "create_worker_event_data",
]

