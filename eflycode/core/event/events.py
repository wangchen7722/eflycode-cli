from typing import Literal

from eflycode.core.event.base import BaseEvent
from eflycode.core.llm.protocol import LLMConfig

class AppStartUpEvent(BaseEvent):
    type: Literal["app.startup"] = "app.startup"

class AppInitializedEvent(BaseEvent):
    type: Literal["app.initialized"] = "app.initialized"

class AppConfigLLMChangedEvent(BaseEvent):
    type: Literal["app.config.llm.changed"] = "app.config.llm.changed"
    source: LLMConfig
    target: LLMConfig

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
