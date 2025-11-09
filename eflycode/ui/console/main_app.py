"""
主应用程序 - UI主线程应用
"""
import threading
import time
from typing import Optional

from eflycode.ui.console.app import ConsoleAgentEventUI
from eflycode.util.event_bus import EventBus
from eflycode.ui.event import UIEventType
from eflycode.util.logger import logger


class MainUIApplication:


    def __init__(self, event_bus: EventBus) -> None:
        """
        初始化主UI应用程序
        
        Args:
            event_bus: 事件总线实例
        """
        self.event_bus = event_bus
        self.ui: Optional[ConsoleAgentEventUI] = None
        self._running = False
        self._shutdown_event = threading.Event()
        
        # 订阅应用控制事件
        self.event_bus.subscribe(UIEventType.STOP_APP, self._on_stop_app, pass_event=False)
        self.event_bus.subscribe(UIEventType.QUIT_UI, self._on_quit_ui, pass_event=False)
        
    def initialize(self) -> None:
        """
        初始化UI组件
        """
        logger.info("初始化UI应用程序...")
        self.ui = ConsoleAgentEventUI(self.event_bus)
        logger.info("UI应用程序初始化完成")
        
        # UI初始化完成后，主动发送欢迎事件
        self.event_bus.emit(UIEventType.SHOW_WELCOME)

    def run(self) -> None:
        """
        启动主UI事件循环
        UI真正运行在主线程中
        """
        if self._running:
            logger.warning("UI应用程序已在运行中")
            return

        # 如果未初始化，先初始化
        if not self.ui:
            self.initialize()

        self._running = True
        logger.info("启动UI主线程事件循环")
        
        try:
            # UI直接在主线程运行（阻塞）
            self.ui.app.run()
            
        except Exception as e:
            logger.exception(f"UI应用程序运行异常: {e}")
        finally:
            self._cleanup()

    def _on_stop_app(self, data: dict) -> None:
        """
        处理停止应用事件
        
        Args:
            data: 事件数据
        """
        logger.info("收到停止应用事件")
        self.stop()

    def _on_quit_ui(self, data: dict) -> None:
        """
        处理UI退出事件（在主线程中执行）
        
        Args:
            data: 事件数据
        """
        logger.info("收到UI退出事件，正在关闭UI...")
        if self.ui and self.ui.app.is_running():
            self.ui.app.exit()

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
        """
        清理资源
        """
        logger.info("清理UI应用程序资源...")
        
        if self.ui:
            try:
                # UI已经在主线程运行，不需要额外停止
                pass
            except Exception as e:
                logger.exception(f"停止UI应用时发生异常: {e}")
                
        logger.info("UI应用程序已停止")