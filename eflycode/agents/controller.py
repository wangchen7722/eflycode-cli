"""
Agent 控制器

管理 Agent 相关的逻辑，包括 Mock Agent 和真实 Agent。
"""
from typing import Optional

from eflycode.agents.mock_agent import MockAgentRunner
from eflycode.util.event_bus import EventBus
from eflycode.util.logger import logger


class AgentController:
    """
    Agent 控制器

    负责管理 Agent 的创建、启动、停止等生命周期操作。
    """

    def __init__(self, event_bus: EventBus, use_mock: bool = True) -> None:
        """
        初始化 Agent 控制器

        Arguments:
            event_bus: 事件总线实例
            use_mock: 是否使用 Mock Agent，默认为 True
        """
        self._event_bus = event_bus
        self._mock_agent: Optional[MockAgentRunner] = None
        self._use_mock = use_mock

        if use_mock:
            self._initialize_mock_agent()

    def _initialize_mock_agent(self) -> None:
        """初始化 Mock Agent"""
        logger.info("初始化 Mock Agent...")
        self._mock_agent = MockAgentRunner(self._event_bus)
        logger.info("Mock Agent 初始化完成")

    @property
    def is_mock_mode(self) -> bool:
        """是否处于 Mock 模式"""
        return self._use_mock

    def start(self) -> None:
        """启动 Agent 控制器"""
        logger.info("Agent 控制器已启动")

    def stop(self) -> None:
        """停止 Agent 控制器"""
        logger.info("停止 Agent 控制器...")
        # 如果需要，可以在这里添加清理逻辑
        logger.info("Agent 控制器已停止")

