"""
应用上下文

维护应用的核心组件：事件总线、UI、控制器等。
"""
from typing import Optional

from eflycode.ui.console.app import ConsoleUI, UIEventHandler
from eflycode.agents.controller import AgentController
from eflycode.util.event_bus import EventBus
from eflycode.util.logger import logger


class ApplicationContext:
    """
    应用上下文

    集中管理应用的核心组件，提供统一的访问接口。
    """

    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        """
        初始化应用上下文

        Arguments:
            event_bus: 事件总线实例，如果为 None 则创建新实例
        """
        self._event_bus = event_bus or EventBus()
        self._ui: Optional[ConsoleUI] = None
        self._event_handler: Optional[UIEventHandler] = None
        self._agent_controller: Optional[AgentController] = None

    @property
    def event_bus(self) -> EventBus:
        """获取事件总线"""
        return self._event_bus

    @property
    def ui(self) -> Optional[ConsoleUI]:
        """获取 UI 实例"""
        return self._ui

    @property
    def event_handler(self) -> Optional[UIEventHandler]:
        """获取事件处理器"""
        return self._event_handler

    @property
    def agent_controller(self) -> Optional[AgentController]:
        """获取 Agent 控制器"""
        return self._agent_controller

    def initialize_ui(self) -> None:
        """初始化 UI 组件"""
        if self._ui is not None:
            logger.warning("UI 已经初始化，跳过重复初始化")
            return

        logger.info("初始化 UI 组件...")
        self._ui = ConsoleUI(self._event_bus)
        self._event_handler = UIEventHandler(self._event_bus, self._ui)
        logger.info("UI 组件初始化完成")

    def initialize_agent_controller(self, use_mock: bool = True) -> None:
        """
        初始化 Agent 控制器

        Arguments:
            use_mock: 是否使用 Mock Agent，默认为 True
        """
        if self._agent_controller is not None:
            logger.warning("Agent 控制器已经初始化，跳过重复初始化")
            return

        logger.info("初始化 Agent 控制器...")
        self._agent_controller = AgentController(self._event_bus, use_mock=use_mock)
        logger.info("Agent 控制器初始化完成")

    def initialize_all(self, use_mock_agent: bool = True) -> None:
        """
        初始化所有组件

        Arguments:
            use_mock_agent: 是否使用 Mock Agent，默认为 True
        """
        self.initialize_ui()
        self.initialize_agent_controller(use_mock=use_mock_agent)

