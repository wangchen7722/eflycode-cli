from typing import Optional, Callable, List
from threading import Lock
import atexit

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

        # 生命周期回调
        self._startup_callbacks: List[Callable[[], None]] = []
        self._shutdown_callbacks: List[Callable[[], None]] = []

        # 状态管理
        self._started = False
        self._shutdown = False
        self._component_lock = Lock()

        # 注册关闭钩子
        atexit.register(self.shutdown)

        logger.info("ApplicationContext 初始化完成")

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

    def get_event_bus(self) -> EventBus:
        """获取事件总线实例

        Returns:
            EventBus实例
        """
        if self._event_bus is None:
            with self._component_lock:
                if self._event_bus is None:
                    self._event_bus = EventBus()
                    logger.info("EventBus 组件已创建")
        return self._event_bus

    def get_environment(self) -> Environment:
        """获取环境配置实例

        Returns:
            Environment实例
        """
        if self._environment is None:
            with self._component_lock:
                if self._environment is None:
                    self._environment = Environment.get_instance()
                    logger.info("Environment 组件已获取")
        return self._environment

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
        if self._started:
            logger.warning("ApplicationContext 已经启动")
            return

        with self._component_lock:
            if self._started:
                return

            logger.info("正在启动 ApplicationContext...")

            try:
                # 初始化核心组件
                environment = self.get_environment()
                logger.info("Environment 组件已初始化")
                
                event_bus = self.get_event_bus()
                logger.info("EventBus 组件已初始化")
                
                # 初始化Advisors
                from eflycode.llm.advisor import initialize_advisors
                initialize_advisors()
                logger.info("Advisors 已初始化")
                
            except Exception as e:
                logger.error(f"核心组件初始化失败: {e}")
                raise

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
        if self._shutdown:
            return

        with self._component_lock:
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

    def create_main_ui_app(self):
        """创建主UI应用程序实例

        工厂方法，负责创建MainUIApplication并注入所需依赖
        这种方式既保持了依赖注入的优势，又将创建逻辑集中管理

        Returns:
            MainUIApplication实例
        """
        from eflycode.ui.console.main_app import MainUIApplication
        
        event_bus = self.get_event_bus()
        return MainUIApplication(event_bus)

    def create_llm_engine(self, advisors=None):
        """创建LLM引擎实例

        工厂方法，负责创建OpenAIEngine并注入所需依赖

        Args:
            advisors: 顾问列表，默认使用标准顾问

        Returns:
            OpenAIEngine实例
        """
        from eflycode.llm.openai_engine import OpenAIEngine
        
        if advisors is None:
            advisors = [
                "buildin_environment_advisor", 
                "buildin_tool_call_advisor", 
                "buildin_logging_advisor"
            ]
        
        environment = self.get_environment()
        return OpenAIEngine(
             llm_config=environment.get_llm_config(),
             advisors=advisors
         )

    def get_agent_registry(self):
        """获取Agent注册中心

        Returns:
            AgentRegistry实例
        """
        from eflycode.agent.registry import AgentRegistry
        return AgentRegistry()

    def create_agent_run_loop(self, agent=None, stream_output=True):
        """创建Agent运行循环实例

        工厂方法，负责创建AgentRunLoop并注入所需依赖

        Args:
            agent: Agent实例，如果为None则自动创建Developer
            stream_output: 是否启用流式输出

        Returns:
            AgentRunLoop实例
        """
        from eflycode.agent.run_loop import AgentRunLoop
        
        if agent is None:
            agent = self.create_developer_agent()
        
        event_bus = self.get_event_bus()
        return AgentRunLoop(
            agent=agent,
            event_bus=event_bus,
            stream_output=stream_output
        )


def get_application_context() -> ApplicationContext:
    """获取应用程序上下文单例实例

    Returns:
        ApplicationContext 实例
    """
    return ApplicationContext.get_instance()
