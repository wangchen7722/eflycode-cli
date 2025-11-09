from typing import Optional, Callable, List
from threading import Lock, RLock
import atexit

from eflycode.llm.advisor.registry import AdvisorRegistry
from eflycode.agent.registry import AgentRegistry
from eflycode.util.event_bus import EventBus
from eflycode.env.environment import Environment
from eflycode.util.logger import logger


class ApplicationContext:
    """应用程序上下文

    负责管理应用程序的核心组件，包括事件总线、环境配置等
    提供统一的组件访问接口和生命周期管理
    """

    _instance: Optional["ApplicationContext"] = None
    _lock = Lock()

    def __init__(self):
        """初始化应用程序上下文"""
        if ApplicationContext._instance is not None:
            raise RuntimeError(
                "ApplicationContext 已经初始化，请使用 get_application_context() 获取实例"
            )

        # 核心组件
        self._event_bus: Optional[EventBus] = None
        self._environment: Optional[Environment] = None
        self._advisor_registry: Optional[AdvisorRegistry] = None
        self._agent_registry: Optional[AgentRegistry] = None

        # 生命周期回调
        self._startup_callbacks: List[Callable[[], None]] = []
        self._shutdown_callbacks: List[Callable[[], None]] = []

        # 状态管理
        self._started = False
        self._shutdown = False

        self._component_lock = RLock()

        # 注册关闭钩子
        atexit.register(self.shutdown)

    @classmethod
    def get_instance(cls) -> "ApplicationContext":
        """获取ApplicationContext单例实例

        Returns:
            ApplicationContext实例
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _init_environment(self) -> None:
        """初始化环境配置"""
        self._environment = Environment()
        logger.info("Environment 组件已初始化")

    def _init_event_bus(self) -> None:
        """初始化事件总线"""
        self._event_bus = EventBus()
        logger.info("EventBus 组件已初始化")

    def _init_llm_advisors(self) -> None:
        """初始化LLM Advisors"""
        self._advisor_registry = AdvisorRegistry()
        logger.info("Advisors 已初始化")

    def _init_agent_registry(self) -> None:
        """初始化Agent Registry"""
        self._agent_registry = AgentRegistry()
        logger.info("AgentRegistry 组件已初始化")

    def get_event_bus(self) -> EventBus:
        """获取事件总线实例

        Returns:
            EventBus实例
        """
        with self._component_lock:
            if not self._started:
                raise RuntimeError("ApplicationContext 未启动，无法获取 EventBus")
            return self._event_bus

    def get_environment(self) -> Environment:
        """获取环境配置实例

        Returns:
            Environment实例
        """
        with self._component_lock:
            if not self._started:
                raise RuntimeError("ApplicationContext 未启动，无法获取 Environment")
            return self._environment

    def get_agent_registry(self):
        """获取Agent注册中心

        Returns:
            AgentRegistry实例
        """
        with self._component_lock:
            if not self._started:
                raise RuntimeError("ApplicationContext 未启动，无法获取 AgentRegistry")
            return self._agent_registry
        
    def get_llm_advisor_registry(self) -> AdvisorRegistry:
        """获取LLM Advisors

        Returns:
            AdvisorRegistry实例
        """
        with self._component_lock:
            if not self._started:
                raise RuntimeError("ApplicationContext 未启动，无法获取 Advisors")
            return self._advisor_registry

    def add_startup_callback(self, callback: Callable[[], None]) -> None:
        """添加启动回调

        Args:
            callback: 启动时执行的回调函数
        """
        self._startup_callbacks.append(callback)

    def add_shutdown_callback(self, callback: Callable[[], None]) -> None:
        """添加关闭回调

        Args:
            callback: 关闭时执行的回调函数
        """
        self._shutdown_callbacks.append(callback)

    def start(self) -> None:
        """启动应用程序上下文"""
        with self._component_lock:
            if self._started:
                logger.warning("ApplicationContext 已经启动")
                return

            try:
                # 初始化核心组件
                self._init_environment()
                self._init_event_bus()
                self._init_llm_advisors()
                self._init_agent_registry()
            except Exception as e:
                raise RuntimeError("ApplicationContext 启动失败") from e

            # 执行启动回调
            for callback in self._startup_callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"启动回调执行失败: {e}")

            self._started = True
            logger.info("ApplicationContext 启动完成")

    def shutdown(self) -> None:
        """关闭应用程序上下文"""
        with self._component_lock:
            if not self._started:
                raise RuntimeError("ApplicationContext 未启动，无法关闭")
            if self._shutdown:
                return

            logger.info("正在关闭 ApplicationContext...")

            # 执行关闭回调
            for callback in reversed(self._shutdown_callbacks):
                try:
                    callback()
                except Exception as e:
                    logger.error(f"关闭回调执行失败: {e}")

            # 关闭事件总线
            if self._event_bus:
                try:
                    self._event_bus.close()
                    logger.info("EventBus 已关闭")
                except Exception as e:
                    logger.error(f"关闭 EventBus 失败: {e}")

            self._shutdown = True
            logger.info("ApplicationContext 关闭完成")

    def is_started(self) -> bool:
        """检查上下文是否已启动

        Returns:
            是否已启动
        """
        return self._started

    def is_shutdown(self) -> bool:
        """检查上下文是否已关闭

        Returns:
            是否已关闭
        """
        return self._shutdown


def get_application_context() -> ApplicationContext:
    """获取应用程序上下文单例实例

    Returns:
        ApplicationContext 实例
    """
    return ApplicationContext.get_instance()
