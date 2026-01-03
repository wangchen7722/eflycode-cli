from typing import Optional
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import Completer
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout.containers import ConditionalContainer, Window, Float
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.layout import CompletionsMenu, Dimension, Float, FloatContainer, HSplit, Layout, MultiColumnCompletionsMenu


class InputWidget(FloatContainer):
    """输入控件"""

    def __init__(
        self,
        buffer: Buffer,
        prompt: str = " > ", 
        placeholder: str = ""
    ):
        self.buffer = buffer
        self.placeholder_text = placeholder
        self.prompt_text = prompt

        self._input_window = self._create_input_window()
        self._placeholder_float = self._create_placeholder_float()
        self._completions_float = self._create_completions_float()
        self._multi_column_completions_float = self._create_multi_column_completions_float()
        self._toolbar_window = self._create_toolbar_window()
        self._empty_window = Window(height=1, char=" ", dont_extend_height=True)

        super().__init__(
            content=HSplit([
                self._input_window,
                self._empty_window,
                self._toolbar_window
            ]),
            floats=[
                self._placeholder_float,
                self._completions_float,
                self._multi_column_completions_float,
            ]
        )

    def _create_input_window(self) -> Window:
        """创建输入窗口"""
        def get_line_prefix(line_number: int, wrap_count: int) -> FormattedText:
            if line_number == 0:
                return FormattedText([("class:prompt", self.prompt_text)])
            else:
                return FormattedText([("class:prompt", " " * len(self.prompt_text))])
        return Window(
            BufferControl(buffer=self.buffer),
            height=Dimension(min=1, max=5, preferred=1),
            wrap_lines=True,
            dont_extend_height=True,
            get_line_prefix=get_line_prefix,
        )

    def _create_placeholder_float(self) -> Float:
        """创建占位符浮层"""
        @Condition
        def placeholder_condition():
            return self.buffer.text.strip() == ""
        
        placeholder_window = ConditionalContainer(
            Window(
                FormattedTextControl(
                    lambda: FormattedText([("class:placeholder", self.placeholder_text)])
                ),
                height=1,
            ),
            filter=placeholder_condition
        )
        return Float(
            left=len(self.prompt_text),
            top=0,
            hide_when_covering_content=True,
            content=placeholder_window,
        )

    def _create_completions_float(self) -> Float:
        """创建补全浮层"""
        return Float(
            xcursor=True,
            ycursor=True,
            transparent=True,
            content=CompletionsMenu(
                max_height=5,
                scroll_offset=1,
                extra_filter=has_focus(self.buffer)
            )
        )

    def _create_multi_column_completions_float(self) -> Float:
        """创建多列补全浮层"""
        return Float(
            xcursor=True,
            ycursor=True,
            transparent=True,
            content=MultiColumnCompletionsMenu(
                extra_filter=has_focus(self.buffer)
            )
        )

    def _create_toolbar_window(self) -> Window:
        """创建工具栏窗口"""
        @Condition
        def toolbar_condition():
            return self.buffer.text.strip() == ""

        def toolbar_content():
            return FormattedText([
                ("class:toolbar.key", "[ @ ]"), ("class:toolbar.label", " Skills "),
                ("", "   "),
                ("class:toolbar.key", "[ # ]"), ("class:toolbar.label", " Files "),
                ("", "   "),
                ("class:toolbar.key", "[ / ]"), ("class:toolbar.label", " Commands "),
            ])
        
        toolbar_window = ConditionalContainer(
            Window(
                FormattedTextControl(toolbar_content),
                height=1,
            ),
            filter=toolbar_condition
        )
        return toolbar_window

    @property
    def input_window(self) -> Window:
        """返回用于聚焦的输入窗口"""
        return self._input_window