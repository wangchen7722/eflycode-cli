"""
主应用程序

负责应用的整体生命周期管理。
"""
import threading
from typing import Optional

from eflycode.context import ApplicationContext
from eflycode.ui.event import UIEventType
from eflycode.util.logger import logger


class MainApplication:
    """
    主应用程序

    负责应用的整体生命周期管理，使用 ApplicationContext 维护核心组件。
    """

    def __init__(self, context: Optional[ApplicationContext] = None) -> None:
        """
        初始化主应用程序

        Arguments:
            context: 应用上下文实例，如果为 None 则创建新实例
        """
        self._context = context or ApplicationContext()
        self._running = False
        self._shutdown_event = threading.Event()
        
        # 订阅应用控制事件
        self._context.event_bus.subscribe(UIEventType.STOP_APP, self._on_stop_app)
        self._context.event_bus.subscribe(UIEventType.QUIT_UI, self._on_quit_ui)

    @property
    def context(self) -> ApplicationContext:
        """获取应用上下文"""
        return self._context
        
    def initialize(self, use_mock_agent: bool = True) -> None:
        """
        初始化所有组件

        Arguments:
            use_mock_agent: 是否使用 Mock Agent，默认为 True
        """
        logger.info("初始化应用程序...")
        self._context.initialize_all(use_mock_agent=use_mock_agent)
        logger.info("应用程序初始化完成")
        
        self._context.event_bus.emit(UIEventType.SHOW_WELCOME)

    def run(self, use_mock_agent: bool = True) -> None:
        """
        启动主UI事件循环

        Arguments:
            use_mock_agent: 是否使用 Mock Agent，默认为 True
        """
        if self._running:
            logger.warning("应用程序已在运行中")
            return

        if not self._context.ui:
            self.initialize(use_mock_agent=use_mock_agent)

        if self._context.agent_controller:
            self._context.agent_controller.start()

        self._running = True
        logger.info("启动UI主线程事件循环")
        
        try:
            self._context.ui.run()
        except Exception as e:
            logger.exception(f"UI应用程序运行异常: {e}")
        finally:
            self._cleanup()

    def _on_stop_app(self, event: str, data: dict) -> None:
        """
        处理停止应用事件
        
        Args:
            data: 事件数据
        """
        logger.info("收到停止应用事件")
        self.stop()

    def _on_quit_ui(self, event: str, data: dict) -> None:
        """处理UI退出事件"""
        logger.info("收到UI退出事件，正在关闭UI...")
        if self._context.ui and self._context.ui.is_running():
            self._context.ui.exit()

    def stop(self) -> None:
        """
        停止UI应用程序
        """
        if not self._running:
            return
            
        logger.info("正在停止UI应用程序...")
        self._running = False
        self._shutdown_event.set()

    def _cleanup(self) -> None:
        """清理资源"""
        logger.info("清理应用程序资源...")
        
        if self._context.agent_controller:
            try:
                self._context.agent_controller.stop()
            except Exception as e:
                logger.exception(f"停止 Agent 控制器时发生异常: {e}")
        
        logger.info("应用程序已停止")

