import threading
from typing import Callable

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.containers import (
    HSplit,
    Window,
    ConditionalContainer,
)
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.application import Application

from .glowing_text_widget import GlowingTextWidget

class ThinkingWidget(ConditionalContainer):
    """思考组件
    """

    def __init__(self, get_app: Callable[[], Application], title: str, content: str = ""):
        """初始化思考组件

        Args:
            get_app (Callable[[], Application]): 应用实例获取函数
            title (str): 思考标题
            content (str): 思考内容
        """
        self.get_app = get_app
        self._thinking = False
        self._lock = threading.Lock()
        self.title = title
        self.content = content or ""
        # 思考标题区域
        self.glow_title = GlowingTextWidget(get_app, self.title, speed=0.05, radius=1)
        # 思考内容区域
        self.buffer = Buffer(read_only=False)
        self.buffer_control = BufferControl(buffer=self.buffer, focusable=False)
        self.scroll_window = Window(
            self.buffer_control,
            height=Dimension(preferred=1, max=10),
            wrap_lines=True,
            right_margins=[ScrollbarMargin(display_arrows=True)],
        )
        # 主容器
        self.container = HSplit([
            self.glow_title,
            self.scroll_window,
        ])
        super().__init__(self.container, filter=Condition(lambda: self._thinking))

    def start_thinking(self):
        """开始思考
        """
        with self._lock:
            self._thinking = True
            self.buffer.text = self.content or ""
            self.glow_title.start()
            self.glow_title.resume()
        self._invalidate()

    def update_title(self, title: str):
        """更新思考标题

        Args:
            title (str): 思考标题
        """
        with self._lock:
            self.title = title
            self.glow_title.update_text(title)
        self._invalidate()

    def append_content(self, text: str):
        """追加思考内容

        Args:
            text (str): 思考内容
        """
        with self._lock:
            self.buffer.text += text
        self._invalidate()

    def stop_thinking(self):
        """停止思考
        """
        with self._lock:
            self._thinking = False
            self.glow_title.stop()
            self.glow_title.pause()
        self._invalidate()

    def clear_content(self):
        """清空思考内容
        """
        with self._lock:
            self.buffer.text = ""
        self._invalidate()

    def _invalidate(self):
        app = None
        try:
            app = self.get_app()
        except Exception:
            pass
        if app:
            app.invalidate()
        