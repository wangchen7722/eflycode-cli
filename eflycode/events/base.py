from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class EventChannel(StrEnum):
    """
    事件通道类型
    """

    UI = "ui"
    WORKER = "worker"
    BRIDGE = "bridge"


class BaseEventPayload(BaseModel):
    """
    事件载荷基类
    """

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """返回序列化字典"""
        return self.model_dump()


TEvent = TypeVar("TEvent", bound=str)
TPayload = TypeVar("TPayload", bound="BaseEventPayload")


@dataclass(frozen=True, slots=True)
class EventEnvelope(Generic[TEvent, TPayload]):
    """
    基础事件封装
    """

    event: TEvent
    payload: TPayload


PayloadBuilder = Callable[[BaseEventPayload], BaseEventPayload]


def serialize_payload(payload: BaseEventPayload) -> dict[str, Any]:
    """
    将载荷序列化为字典
    """

    return payload.model_dump()

