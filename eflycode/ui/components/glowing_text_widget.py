import time
import threading
from typing import Callable
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.application import Application


class GlowingTextWidget(Window):
    """闪烁文本组件
    """

    def __init__(self, get_app: Callable[[], Application], text: str, speed: float = 0.05, radius: int = 1, **kwargs):
        """初始化闪烁文本组件

        Args:
            get_app (Callable[[], Application]): 应用实例获取函数
            text (str): 要显示的文本
            speed (float, optional): 闪烁速度，单位为秒. Defaults to 0.05.
            radius (int, optional): 闪烁半径，即文本前后的空格数. Defaults to 1.
        """
        self._get_app = get_app
        self.text = text
        self.speed = speed
        self.radius = radius
        self.control = FormattedTextControl(self._get_formatted_text)
        super().__init__(self.control, dont_extend_height=True, **kwargs)

        self._highlight_index = 0
        self._running = False
        self._enabled = True
        self._lock = threading.Lock()
        self._thread = None

    def start(self):
        """启动组件运行
        """
        if self._running:
            return
        self._running = True
        self._enabled = True
        if self._thread is None:
            self._thread = threading.Thread(target=self._animate, daemon=True)
            self._thread.start()
        else:
            if not self._thread.is_alive():
                self._thread.start()

    def _get_formatted_text(self) -> FormattedText:
        """获取格式化文本

        Returns:
            FormattedText: 格式化文本
        """
        with self._lock:
            if not self.text:
                return FormattedText([("class:glowing.text.normal", "")])
            
            parts = []
            for i, ch in enumerate(self.text):
                if not self._enabled:
                    parts.append(("class:glowing.text.paused", ch))
                    continue

                dist = abs(i - self._highlight_index)
                if dist == 0:
                    style = "class:glowing.text.center"
                elif dist == 1 and self.radius >= 1:
                    style = "class:glowing.text.near"
                elif dist == 2 and self.radius >= 2:
                    style = "class:glowing.text.far"
                else:
                    style = "class:glowing.text.normal"
                parts.append((style, ch))
            return FormattedText(parts)

    def _animate(self):
        """动画线程，用于更新闪烁索引
        """
        while self._running:
            if self._enabled and self.text and len(self.text) > 0 and self.radius > 0:
                with self._lock:
                    self._highlight_index = (self._highlight_index + 1) % (len(self.text) + self.radius)
                self._invalidate()
                time.sleep(self.speed)
            else:
                time.sleep(self.speed)
                self._invalidate()

    def _invalidate(self):
        """刷新组件显示
        """
        try:
            if self._get_app():
                self._get_app().invalidate()
        except Exception as e:
            print(f"Error in GlowingTextWidget._invalidate: {e}")
            pass

    def update_text(self, text: str):
        """更新组件显示的文本

        Args:
            text (str): 要显示的文本
        """
        with self._lock:
            self.text = text
            self._highlight_index = 0
        self._invalidate()

    def toggle(self):
        """切换组件是否运行
        """
        with self._lock:
            self._enabled = not self._enabled
        self._invalidate()

    def pause(self):
        """暂停组件运行
        """
        with self._lock:
            self._enabled = False
        self._invalidate()

    def resume(self):
        """恢复组件运行
        """
        with self._lock:
            self._enabled = True
        self._invalidate()

    def stop(self):
        """停止组件运行
        """
        self._running = False

