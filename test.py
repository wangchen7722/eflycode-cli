# test_thinking_widget.py
import time
from prompt_toolkit.application import Application
from prompt_toolkit.layout import Layout, HSplit
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.styles import Style

from eflycode.ui.components.thinking_widget import ThinkingWidget
from eflycode.ui.components.glowing_text_widget import GlowingTextWidget
from eflycode.ui.colors import PTK_STYLE


def main():
    kb = KeyBindings()
    app_ref = [None]

    # 创建思考组件
    thinking = ThinkingWidget(lambda: app_ref[0], "🤔 Thinking...", "")

    # 布局
    layout = Layout(HSplit([
        thinking,
    ]))

    # 样式
    base_style = Style.from_dict({
        "glowing.text.normal": "fg:#777777",
        "glowing.text.far": "fg:#aaaaaa",
        "glowing.text.near": "fg:#dddddd",
        "glowing.text.center": "fg:#ffffff bold",
        "glowing.text.paused": "fg:#555555 italic",
    })
    style = merge_styles([base_style, PTK_STYLE])

    app = Application(
        layout=layout,
        key_bindings=kb,
        style=style,
        full_screen=False,
    )
    app_ref[0] = app

    # 绑定键盘事件
    @kb.add(Keys.ControlS)
    def _(event):
        thinking.start_thinking()
        thinking.append_content("Thinking deeply about something...")
        thinking.append_content("Analyzing data...")
        thinking.append_content("Drawing conclusions...")
        event.app.invalidate()

    @kb.add(Keys.ControlE)
    def _(event):
        thinking.stop_thinking()

    @kb.add(Keys.ControlC)
    def _(event):
        event.app.exit()

    app.run()


if __name__ == "__main__":
    main()
