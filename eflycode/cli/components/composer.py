import asyncio
from typing import Awaitable, Callable, List, Optional, Union

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import Completer
from prompt_toolkit.filters import has_focus
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import CompletionsMenu, Layout
from prompt_toolkit.layout.containers import (
    Float,
    FloatContainer,
    HSplit,
    Window,
)
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension

from eflycode.core.ui.style import build_prompt_toolkit_style
from eflycode.core.ui.errors import UserCanceledError

def build_get_line_prefix(
    prompt_text: str,
    busy_prompt_text: str,
    get_prompt_width: Callable[[], int],
    on_busy: Optional[Callable[[], bool]] = None,
) -> Callable[[int, int], FormattedText]:
    def _get_line_prefix(line_number: int, wrap_count: int) -> FormattedText:
        prompt = prompt_text
        if on_busy is not None and on_busy():
            prompt = busy_prompt_text
        if line_number == 0:
            return FormattedText([("class:composer.prompt", prompt)])
        return FormattedText([("class:composer.prompt", " " * get_prompt_width())])
    return _get_line_prefix

def build_get_line_prefix_width(
    prompt_text: str,
    busy_prompt_text: str,
    on_busy: Optional[Callable[[], bool]] = None,
) -> int:
    def _get_line_prefix_width() -> int:
        prompt = prompt_text
        if on_busy is not None and on_busy():
            prompt = busy_prompt_text
        return len(prompt)
    return _get_line_prefix_width

def build_placeholder_visible(buffer: Buffer) -> Callable[[], bool]:
    def _placeholder_visible() -> bool:
        return buffer.text.strip() == ""
    return _placeholder_visible


class ComposerComponent:

    async def show(
        self,
        *,
        prompt_text: str = "> ",
        busy_prompt_text: str = "> ",
        placeholder: str = "share your ideas...",
        toolbar_text: Optional[str] = None,
        multiline: bool = True,
        min_height: int = 1,
        max_height: int = 20,
        completer: Optional[Completer] = None,
        on_complete: Optional[Union[Callable[[str], bool], Callable[[str], Awaitable[bool]]]] = None,
        on_busy: Optional[Callable[[], bool]] = None,
    ) -> str:
        buffer = Buffer(
            completer=completer,
            multiline=multiline
        )
        get_prompt_width = build_get_line_prefix_width(prompt_text, busy_prompt_text, on_busy)

        input_window = Window(
            content=BufferControl(buffer=buffer),
            height=Dimension(min=min_height, max=max_height),
            wrap_lines=True,
            dont_extend_height=True,
            get_line_prefix=build_get_line_prefix(prompt_text, busy_prompt_text, get_prompt_width, on_busy),
        )
        placeholder_float = Float(
            left=get_prompt_width(),
            top=0,
            hide_when_covering_content=True,
            content=Window(
                content=FormattedTextControl(
                    lambda: FormattedText([("class:composer.placeholder", placeholder)])
                ),
                height=1,
                dont_extend_height=True,
            ),
        )
        completions_float = Float(
            xcursor=True,
            ycursor=True,
            transparent=True,
            content=CompletionsMenu(
                scroll_offset=1,
                extra_filter=has_focus(buffer)
            )
        )
        toolbar_window = Window(
            content=FormattedTextControl(lambda: FormattedText([("class:composer.toolbar", toolbar_text)])),
            height=1,
            dont_extend_height=True,
        )

        kb = KeyBindings()

        @kb.add(Keys.Enter)
        def _on_enter(event: KeyPressEvent):
            if event.current_buffer.complete_state:
                completion = event.current_buffer.complete_state.current_completion
                if completion is not None:
                    event.current_buffer.apply_completion(completion)
                    return
            event.current_buffer.insert_text("\n")
        
        @kb.add(Keys.ControlM)
        def _on_submit(event: KeyPressEvent):
            text = event.current_buffer.text.strip()
            # 检查是否是命令，以 / 开头
            if text.startswith("/"):
                # 处理命令
                if on_complete:
                    # 检查是否是异步函数
                    if asyncio.iscoroutinefunction(on_complete):
                        # 异步回调，在事件循环中运行
                        # 由于我们在异步上下文中，使用 app.run_async，可以使用 create_task
                        loop = asyncio.get_event_loop()
                        task = loop.create_task(on_complete(text))
                        # 使用回调来处理结果
                        def handle_result(future):
                            try:
                                handled = future.result()
                                if handled:
                                    # 在事件循环中调用 exit
                                    # 使用 call_soon 确保在正确的上下文中调用
                                    loop.call_soon(event.app.exit, result="")
                            except Exception:
                                pass
                        task.add_done_callback(handle_result)
                        return
                    else:
                        # 同步回调
                        handled = on_complete(text)
                        if handled:
                            # 命令已处理，退出并返回空字符串，让主循环继续
                            event.app.exit(result="")
                            return
            # 普通输入，退出并返回结果
            event.app.exit(result=text)
        
        @kb.add(Keys.Tab)
        def _on_tab(event: KeyPressEvent):
            if completer is None:
                return
            event.current_buffer.start_completion(select_first=False)
        
        @kb.add(Keys.ControlD)
        def _on_cancel(event: KeyPressEvent):
            event.app.exit(result=None)

        def _container_contents() -> List[Window]:
            contents = [input_window]
            if toolbar_text is not None:
                contents.append(toolbar_window)
            return contents
        
        def _container_floats() -> List[Float]:
            floats = [placeholder_float]
            if completer is not None:
                floats.append(completions_float)
            return floats
        
        root = FloatContainer(
            content=HSplit(_container_contents()),
            floats=_container_floats(),
        )

        app = Application(
            layout=Layout(root, focused_element=input_window),
            key_bindings=kb,
            style=build_prompt_toolkit_style(),
            full_screen=False,
            erase_when_done=True,
            mouse_support=False
        )
        result = await app.run_async()
        if result is None:
            raise UserCanceledError()

        return str(result)
        

def main():
    import asyncio
    async def _main():
        composer = ComposerComponent()
        result = await composer.show()
        print(result)
    asyncio.run(_main())

if __name__ == "__main__":
    main()
