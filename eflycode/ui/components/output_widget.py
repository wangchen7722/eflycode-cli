from __future__ import annotations

import threading
from typing import Callable

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin


class OutputWidget(Window):
    """
    Read-only scrollable output panel backed by a prompt_toolkit Buffer.
    """

    def __init__(self, get_app: Callable[[], Application], height: int = 10) -> None:
        """
        Arguments:
            get_app: Callback returning the running Application instance.
            height: Preferred visible height for the output window.

        Return Values:
            None

        Exceptions:
            None
        """
        self._get_app = get_app
        self._lock = threading.Lock()
        self._buffer = Buffer(read_only=True, multiline=True)

        control = BufferControl(buffer=self._buffer, focusable=False)
        super().__init__(
            content=control,
            height=Dimension(min=1, max=height, preferred=height),
            wrap_lines=True,
            right_margins=[ScrollbarMargin(display_arrows=True)],
            dont_extend_height=False,
        )

    def append(self, text: str) -> None:
        """
        Append text to the output buffer and move cursor to the end.

        Arguments:
            text: Content to append.

        Return Values:
            None

        Exceptions:
            None
        """
        with self._lock:
            self._buffer.read_only = False
            new_content = self._buffer.text + text
            self._buffer.text = new_content
            self._buffer.cursor_position = len(new_content)
            self._buffer.read_only = True
        self._invalidate()

    def clear(self) -> None:
        """
        Clear all content from the output buffer.

        Arguments:
            None

        Return Values:
            None

        Exceptions:
            None
        """
        with self._lock:
            self._buffer.read_only = False
            self._buffer.text = ""
            self._buffer.cursor_position = 0
            self._buffer.read_only = True
        self._invalidate()

    def _invalidate(self) -> None:
        """
        Request a UI redraw if the Application is available.
        """
        try:
            app = self._get_app()
            if app:
                app.invalidate()
        except Exception:
            pass

