from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID, uuid4
from datetime import datetime

class BaseEvent(BaseModel):
    model_config = ConfigDict(
        forzen=True, extra="allow"
    )
    v: int = 1
    event_id: UUID = Field(default_factory=uuid4)
    ts: datetime = Field(default_factory=datetime.now)
    
    type: str

class AppStartUpEvent(BaseEvent):
    type: Literal["app.startup"] = "app.startup"

class AppShutDownEvent(BaseEvent):
    type: Literal["app.shutdown"] = "app.shutdown"

class AgentEvent(BaseEvent):
    ...

class AgentTaskStartEvent(AgentEvent):
    type: Literal["agent.task.start"] = "agent.task.start"

class AgentTaskStopEvent(AgentEvent):
    type: Literal["agent.task.stop"] = "agent.task.stop"

class AgentTaskPauseEvent(AgentEvent):
    type: Literal["agent.task.pause"] = "agent.task.pause"

class AgentTaskResumeEvent(AgentEvent):
    type: Literal["agent.task.resume"] = "agent.task.resume"

class AgentMessageStartEvent(AgentEvent):
    type: Literal["agent.message.start"] = "agent.message.start"

class AgentMessageDeltaEvent(AgentEvent):
    type: Literal["agent.message.delta"] = "agent.message.delta"

class AgentMessageStopEvent(AgentEvent):
    type: Literal["agent.message.stop"] = "agent.message.stop"

class AgentToolCallEvent(AgentEvent):
    type: Literal["agent.tool.call"] = "agent.tool.call"