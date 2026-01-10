from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class BaseEvent(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="allow"
    )
    v: int = 1
    event_id: UUID = Field(default_factory=uuid4)
    ts: datetime = Field(default_factory=datetime.now)

    type: str
