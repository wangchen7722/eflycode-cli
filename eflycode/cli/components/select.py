from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from prompt_toolkit.application import Application
from prompt_toolkit.data_structures import Point
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import HSplit, Layout
from prompt_toolkit.layout.containers import ScrollOffsets, Window
from prompt_toolkit.layout.controls import FormattedTextControl

from eflycode.core.ui.errors import UserCanceledError
from eflycode.core.ui.style import build_prompt_toolkit_style


@dataclass(frozen=True)
class _SelectOption:
    key: str
    label: str
    description: Optional[str] = None
    disabled: bool = False



class SelectComponent:
    async def show(
        self,
        *,
        title: str,
        options: List[Dict[str, Any]],
        default_key: str | None = None,
        full_screen: bool = False,
        erase_when_done: bool = True,
    ) -> Tuple[int, str]:
        normalized_options = self._normalize_options(options)
        if not normalized_options:
            raise ValueError("SelectListComponent.show(): 'options' must not be empty.")

        enabled_indices = [
            i for i, opt in enumerate(normalized_options) if not opt.disabled
        ]
        if not enabled_indices:
            raise ValueError(
                "SelectListComponent.show(): all options are disabled; nothing can be selected."
            )

        selected_index = self._select_initial_index(
            normalized_options=normalized_options,
            default_key=default_key,
            fallback_index=enabled_indices[0],
        )

        # Used to keep the selected item visible via cursor position.
        option_start_line_by_index: List[int] = [0] * len(normalized_options)

        def _build_title_text() -> StyleAndTextTuples:
            return [("class:select.title", title)]

        def _build_formatted_text() -> StyleAndTextTuples:
            nonlocal option_start_line_by_index

            fragments: StyleAndTextTuples = []
            current_line = 0

            for idx, opt in enumerate(normalized_options):
                option_start_line_by_index[idx] = current_line

                is_selected = idx == selected_index
                if opt.disabled:
                    base_style = "class:select.option.disabled"
                elif is_selected:
                    base_style = "class:select.option.selected"
                else:
                    base_style = "class:select.option"

                prefix = "❯ " if is_selected else "  "
                label_text = opt.label + (" [disabled]" if opt.disabled else "")

                fragments.append((base_style, prefix))
                fragments.append((base_style, label_text))
                fragments.append(("", "\n"))
                current_line += 1

                if opt.description:
                    if opt.disabled:
                        desc_style = "class:select.option.description.disabled"
                    else:
                        desc_style = "class:select.option.description"
                    fragments.append((desc_style, f"    {opt.description}"))
                    fragments.append(("", "\n"))
                    current_line += 1

            # Trim trailing newline if present.
            if fragments and fragments[-1] == ("", "\n"):
                fragments.pop()

            return fragments

        def _get_cursor_position() -> Point:
            y = option_start_line_by_index[selected_index]
            return Point(x=0, y=y)

        title_window = Window(
            content=FormattedTextControl(text=_build_title_text, focusable=False),
            height=1,
            dont_extend_height=True,
            always_hide_cursor=True,
        )

        text_control = FormattedTextControl(
            text=_build_formatted_text,
            focusable=True,
            show_cursor=False,
            get_cursor_position=_get_cursor_position,
        )

        body_window = Window(
            content=text_control,
            wrap_lines=False,
            always_hide_cursor=True,
            scroll_offsets=ScrollOffsets(top=1, bottom=1),
        )

        kb = KeyBindings()

        def _move(delta: int) -> None:
            nonlocal selected_index
            selected_index = self._move_selection(
                normalized_options=normalized_options,
                current_index=selected_index,
                delta=delta,
            )

        @kb.add(Keys.Up)
        def _on_up(event: KeyPressEvent) -> None:  # noqa: ANN001
            _move(-1)

        @kb.add(Keys.Down)
        def _on_down(event: KeyPressEvent) -> None:  # noqa: ANN001
            _move(+1)

        @kb.add(Keys.Enter)
        def _on_enter(event: KeyPressEvent) -> None:  # noqa: ANN001
            current = normalized_options[selected_index]
            if current.disabled:
                return
            event.app.exit(result=current.key)

        @kb.add(Keys.Escape)
        def _on_escape(event: KeyPressEvent) -> None:  # noqa: ANN001
            event.app.exit(result=None)

        @kb.add(Keys.ControlC)
        def _on_ctrl_c(event: KeyPressEvent) -> None:  # noqa: ANN001
            event.app.exit(result=None)

        style = build_prompt_toolkit_style()

        root_container = HSplit([title_window, body_window])
        app = Application(
            layout=Layout(container=root_container, focused_element=body_window),
            key_bindings=kb,
            style=style,
            full_screen=full_screen,
            erase_when_done=erase_when_done,
            mouse_support=False,
        )
        
        result = await app.run_async()
        if result is None:
            raise UserCanceledError()

        return str(result)

    @staticmethod
    def _normalize_options(options: List[Dict[str, Any]]) -> List[_SelectOption]:
        normalized: List[_SelectOption] = []

        for raw in options:
            key = str(raw.get("key", "")).strip()
            label = str(raw.get("label", "")).strip()
            if not key or not label:
                raise ValueError("Each option must have non-empty key and label.")
            description_raw = raw.get("description", None)
            description = (
                str(description_raw).strip() if description_raw is not None else None
            )
            description = description or None

            disabled = bool(raw.get("disabled", False))

            normalized.append(
                _SelectOption(
                    key=key, label=label, description=description, disabled=disabled
                )
            )

        return normalized

    @staticmethod
    def _select_initial_index(
        *,
        normalized_options: List[_SelectOption],
        default_key: str | None,
        fallback_index: int,
    ) -> int:
        if default_key:
            for idx, opt in enumerate(normalized_options):
                if opt.key == default_key and not opt.disabled:
                    return idx
        return fallback_index

    @staticmethod
    def _move_selection(
        *,
        normalized_options: List[_SelectOption],
        current_index: int,
        delta: int,
    ) -> int:
        """
        Move selection by delta, skipping disabled options, wrapping around.

        Args:
            normalized_options: The list of normalized options.
            current_index: The current index of the selected option.
            delta: The delta to move the selection by.

        Returns:
            The new index of the selected option.
        """
        if delta == 0:
            return current_index

        count = len(normalized_options)
        next_index = current_index

        for _ in range(count):
            next_index = (next_index + delta) % count
            if not normalized_options[next_index].disabled:
                return next_index

        # Should not happen because we pre-check "all disabled", but keep safe.
        return current_index


def main() -> None:
    import asyncio
    component = SelectComponent()
    result = asyncio.run(component.show(
        title="play",
        options=[
            {"key": "1", "label": "play"},
            {"key": "2", "label": "pause"},
            {"key": "3", "label": "stop"},
        ],
        default_key="2",
        full_screen=False,
    ))
    print("result:", result)


if __name__ == "__main__":
    main()
