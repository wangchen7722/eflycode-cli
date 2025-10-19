from abc import ABC, abstractmethod
from typing import Dict, Callable

from eflycode.util.logger import logger
from eflycode.util.event_bus import EventBus


class UIEventType:
    """
    UI事件类型
    """
    START_APP = "start_app"
    STOP_APP = "stop_app"

    SHOW_WELCOME = "show_welcome"
    PROGRESS_START = "progress_start"
    PROGRESS_UPDATE = "progress_update"
    PROGRESS_END = "progress_end"
    FILE_OPEN = "file_open"
    FILE_UPDATE = "file_update"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    USER_INPUT = "user_input"
    USER_INPUT_RECEIVED = "user_input_received"
    USER_CONFIRM = "user_confirm"


class AgentUIEventType(UIEventType):
    """
    Agent UI事件类型
    """
    THINK_START = "think_start"
    THINK_UPDATE = "think_update"
    THINK_END = "think_end"

    MESSAGE_START = "message_start"
    MESSAGE_UPDATE = "message_update"
    MESSAGE_END = "message_end"

    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_END = "tool_call_end"
    TOOL_CALL_FINISH = "tool_call_finish"
    TOOL_CALL_ERROR = "tool_call_error"

    CODE_DIFF = "code_diff"
    TERMINAL_EXEC_START = "terminal_exec_start"
    TERMINAL_EXEC_RUNNING = "terminal_exec_running"
    TERMINAL_EXEC_END = "terminal_exec_end"


class UIEventHandlerMixin(ABC):
    """
    UI事件处理程序 Mixin
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_handlers: Dict[str, Callable[[dict], None]] = {}
        self._event_bus = event_bus
        
        # 订阅事件总线事件
        self._event_bus.subscribe(UIEventType.START_APP, self.handle_event)
        self._event_bus.subscribe(UIEventType.STOP_APP, self.handle_event)
        self._event_bus.subscribe(UIEventType.SHOW_WELCOME, self.handle_event)
        self._event_bus.subscribe(UIEventType.PROGRESS_START, self.handle_event)
        self._event_bus.subscribe(UIEventType.PROGRESS_UPDATE, self.handle_event)
        self._event_bus.subscribe(UIEventType.PROGRESS_END, self.handle_event)
        self._event_bus.subscribe(UIEventType.FILE_OPEN, self.handle_event)
        self._event_bus.subscribe(UIEventType.FILE_UPDATE, self.handle_event)
        self._event_bus.subscribe(UIEventType.INFO, self.handle_event)
        self._event_bus.subscribe(UIEventType.WARNING, self.handle_event)
        self._event_bus.subscribe(UIEventType.ERROR, self.handle_event)
        self._event_bus.subscribe(UIEventType.USER_INPUT, self.handle_event)
        self._event_bus.subscribe(UIEventType.USER_CONFIRM, self.handle_event)

    def register_event_handler(self, event: str, handler: Callable[[dict], None]) -> None:
        """注册单个事件处理函数"""
        if event in self._event_handlers:
            raise ValueError(f"事件 {event} 已注册处理函数")
        self._event_handlers[event] = handler
        
    def handle_event(self, event: str, data: dict) -> None:
        """处理事件"""
        print(f"handle_event: {event} {data}")
        handler = self._event_handlers.get(event)
        if handler:
            handler(data)
        else:
            # 尝试默认实现方法
            handler_fn = f"_handle_{event}"
            if hasattr(self, handler_fn):
                getattr(self, handler_fn)(data)
            else:
                logger.warning(f"未注册处理函数的事件 {event}")

    @abstractmethod
    def _handle_start_app(self, data: dict) -> None:
        """处理启动应用事件"""
        ...

    @abstractmethod
    def _handle_stop_app(self, data: dict) -> None:
        """处理停止应用事件"""
        ...

    @abstractmethod
    def _handle_show_welcome(self, data: dict) -> None:
        """处理欢迎事件"""
        ...

    @abstractmethod
    def _handle_progress_start(self, data: dict) -> None:
        """处理进度开始事件"""
        ...

    @abstractmethod
    def _handle_progress_update(self, data: dict) -> None:
        """处理进度更新事件"""
        ...

    @abstractmethod
    def _handle_progress_end(self, data: dict) -> None:
        """处理进度结束事件"""
        ...

    @abstractmethod
    def _handle_file_open(self, data: dict) -> None:
        """处理文件打开事件"""
        ...

    @abstractmethod
    def _handle_file_update(self, data: dict) -> None:
        """处理文件更新事件"""
        ...

    @abstractmethod
    def _handle_info(self, data: dict) -> None:
        """处理信息事件"""
        ...

    @abstractmethod
    def _handle_warning(self, data: dict) -> None:
        """处理警告事件"""
        ...

    @abstractmethod
    def _handle_error(self, data: dict) -> None:
        """处理错误事件"""
        ...

    @abstractmethod
    def _handle_user_input(self, data: dict) -> None:
        """处理用户输入事件"""
        ...

    @abstractmethod
    def _handle_user_confirm(self, data: dict) -> None:
        """处理用户确认事件"""
        ...


class AgentUIEventHandlerMixin(UIEventHandlerMixin):
    """
    Agent UI事件处理程序 Mixin
    """
    
    def __init__(self, event_bus: EventBus) -> None:
        super().__init__(event_bus)
        
        # 订阅事件总线
        self._event_bus.subscribe(AgentUIEventType.THINK_START, self.handle_event)
        self._event_bus.subscribe(AgentUIEventType.THINK_UPDATE, self.handle_event)
        self._event_bus.subscribe(AgentUIEventType.THINK_END, self.handle_event)
        
        # 订阅消息事件
        self._event_bus.subscribe(AgentUIEventType.MESSAGE_START, self.handle_event)
        self._event_bus.subscribe(AgentUIEventType.MESSAGE_UPDATE, self.handle_event)
        self._event_bus.subscribe(AgentUIEventType.MESSAGE_END, self.handle_event)
        
        # 订阅工具调用事件
        self._event_bus.subscribe(AgentUIEventType.TOOL_CALL_START, self.handle_event)
        self._event_bus.subscribe(AgentUIEventType.TOOL_CALL_END, self.handle_event)
        self._event_bus.subscribe(AgentUIEventType.TOOL_CALL_FINISH, self.handle_event)
        self._event_bus.subscribe(AgentUIEventType.TOOL_CALL_ERROR, self.handle_event)
        
        # 订阅代码差异事件
        self._event_bus.subscribe(AgentUIEventType.CODE_DIFF, self.handle_event)
        
        # 订阅终端执行事件
        self._event_bus.subscribe(AgentUIEventType.TERMINAL_EXEC_START, self.handle_event)
        self._event_bus.subscribe(AgentUIEventType.TERMINAL_EXEC_RUNNING, self.handle_event)
        self._event_bus.subscribe(AgentUIEventType.TERMINAL_EXEC_END, self.handle_event)
        
        
    @abstractmethod
    def _handle_think_start(self, data: dict) -> None:
        """处理思考开始事件"""
        ...
        
    @abstractmethod
    def _handle_think_update(self, data: dict) -> None:
        """处理思考更新事件"""
        ...
        
    @abstractmethod
    def _handle_think_end(self, data: dict) -> None:
        """处理思考结束事件"""
        ...
        
    @abstractmethod
    def _handle_message_start(self, data: dict) -> None:
        """处理消息开始事件"""
        ...
        
    @abstractmethod
    def _handle_message_update(self, data: dict) -> None:
        """处理消息更新事件"""
        ...
        
    @abstractmethod
    def _handle_message_end(self, data: dict) -> None:
        """处理消息结束事件"""
        ...
        
    @abstractmethod
    def _handle_tool_call_start(self, data: dict) -> None:
        """处理工具调用开始事件"""
        ...
        
    @abstractmethod
    def _handle_tool_call_end(self, data: dict) -> None:
        """处理工具调用结束事件"""
        ...
        
    @abstractmethod
    def _handle_tool_call_finish(self, data: dict) -> None:
        """处理工具调用完成事件"""
        ...
        
    @abstractmethod
    def _handle_tool_call_error(self, data: dict) -> None:
        """处理工具调用错误事件"""
        ...
        
    @abstractmethod
    def _handle_code_diff(self, data: dict) -> None:
        """处理代码差异事件"""
        ...
        
    @abstractmethod
    def _handle_terminal_exec_start(self, data: dict) -> None:
        """处理终端执行开始事件"""
        ...
        
    @abstractmethod
    def _handle_terminal_exec_running(self, data: dict) -> None:
        """处理终端执行运行事件"""
        ...
        
    @abstractmethod
    def _handle_terminal_exec_end(self, data: dict) -> None:
        """处理终端执行结束事件"""
        ...
