from typing import Callable, List, Optional

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

    def show(
        self,
        *,
        prompt_text: str = "> ",
        busy_prompt_text: str = "🤔> ",
        placeholder: str = "share your ideas...",
        toolbar_text: Optional[str] = None,
        multiline: bool = True,
        min_height: int = 1,
        max_height: int = 20,
        completer: Optional[Completer] = None,
        on_complete: Optional[Callable[[str], bool]] = None,
        on_busy: Optional[Callable[[], bool]] = None,
    ) -> None:
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
        
        @kb.add(Keys.ControlJ)
        def _on_submit(event: KeyPressEvent):
            event.app.exit(result=event.current_buffer.text)
        
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
        result = app.run()
        if result is None:
            raise UserCanceledError()

        return str(result)
        

def main():
    composer = ComposerComponent()
    result = composer.show()
    print(result)

if __name__ == "__main__":
    main()
