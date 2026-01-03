# UI System Architecture

## Overview

The project implements a console-based UI system using an abstract interface pattern and event-driven architecture, built on `prompt_toolkit` and `rich` libraries.

## 1. Architecture Design

### Layered Architecture

- **Abstract Layer**: `BaseUI` defines unified interface
- **Implementation Layer**: `ConsoleUI` provides console implementation
- **Component Layer**: Reusable Widget components
- **Event Layer**: Event bus-based communication mechanism

```
eflycode/ui/
├── base_ui.py              # Abstract base class
├── base_controller.py      # UI controller base class
├── event.py                # Event definitions
├── colors.py               # Color scheme
├── console/
│   ├── app.py             # ConsoleUI main implementation
│   └── ui.py              # BaseConsoleUI base implementation
└── components/
    ├── input_widget.py    # Input component
    ├── thinking_widget.py # Thinking state component
    ├── glowing_text_widget.py # Glowing text component
    └── output_widget.py   # Output component
```

## 2. Core Components

### BaseUI (Abstract Base Class)

Defines UI interface contract, including:

- **Basic Display**: `print()`, `info()`, `error()`, `success()`, `warning()`
- **User Interaction**: `choices()` for selection lists
- **Advanced Display**: `panel()`, `table()`, `progress()`, `help()`
- **System Control**: `welcome()`, `clear()`, `flush()`, `exit()`

### ConsoleUI (Console Implementation)

Located in `eflycode/ui/console/app.py`, key features:

- **State Management**: Three states: `INPUT`, `TOOL_CALL`, `THINKING`
- **Thread Safety**: Uses locks to protect UI operations
- **Rich Rendering**: Renders through StringIO buffer, then outputs via prompt_toolkit
- **Dynamic Layout**: Switches layouts based on state

```python
class UIState(Enum):
    INPUT = "input"
    TOOL_CALL = "tool_call"
    THINKING = "thinking"
```

## 3. UI Components

### InputWidget (Input Component)

Features:
- Multi-line input support
- Auto-completion (single/multi-column)
- History management (FileHistory)
- Placeholder hints
- Toolbar hints (shortcuts)

### ThinkingWidget (Thinking State Component)

Features:
- Displays Agent thinking process
- Streams content in real-time
- Uses `GlowingTextWidget` for animated title
- Scrollable content area

### GlowingTextWidget (Glowing Text Component)

Features:
- Text glowing animation effect
- Configurable speed and radius
- Supports pause/resume
- Independent animation thread

## 4. Event-Driven Architecture

### Event Types

- **Basic UI Events**: `START_APP`, `STOP_APP`, `SHOW_WELCOME`, `CLEAR_SCREEN`, etc.
- **Agent Events**: `THINK_START`, `THINK_UPDATE`, `THINK_END`, `TOOL_CALL_START`, etc.

### UIEventHandler

- Subscribes to event bus
- Converts events to UI operations
- Uses `run_ui()` to ensure UI operations execute on correct thread

## 5. Technical Features

### Keyboard Bindings

- `Ctrl+C`: Interrupt current task or exit application
- `Enter`: Submit input
- `Alt+Enter`: Insert newline
- `Backspace`: Delete and trigger completion (when input is `/`, `#`, `@`)

### Color System

Unified color definitions (`colors.py`):
- Supports both prompt_toolkit and rich
- Semantic colors (success, warning, error, info)
- Code syntax highlighting colors

### Thread Safety

- `run_ui()` ensures UI operations execute on UI thread
- Uses locks to protect shared state
- Supports calling UI methods from any thread

## 6. Workflow

1. **Initialization**: Creates `ConsoleUI` and `UIEventHandler`
2. **User Input**: Captured through `InputWidget`, triggers `USER_INPUT_RECEIVED` event
3. **State Switching**: Switches UI layout based on Agent state
4. **Streaming Output**: Appends thinking/message content in real-time
5. **Tool Calls**: Displays tool call status and results

## 7. Design Highlights

1. **Abstract Interface**: Easy to extend with other UI implementations (e.g., Web UI)
2. **Event Decoupling**: UI and business logic decoupled via event bus
3. **State Management**: Clear state machine for UI state management
4. **Componentization**: Reusable Widget components
5. **Thread Safety**: Supports UI updates in multi-threaded environments
6. **User Experience**: Smooth interactions, animated feedback, auto-completion

## 8. Key Implementation Details

### Rich Integration

The system uses Rich library for rendering, but outputs through prompt_toolkit to avoid screen management conflicts:

```python
def _print_rich(self, *args, end: str = "\n", **kwargs) -> None:
    """
    Render text using rich, then output through prompt_toolkit's print_formatted_text.
    
    This maintains rich's style support while avoiding interference with prompt_toolkit's screen management.
    """
    self._render_buffer.seek(0)
    self._render_buffer.truncate(0)
    self._render_console.print(*args, end=end, **kwargs)
    rendered = self._render_buffer.getvalue()
    if rendered:
        print_formatted_text(ANSI(rendered), end="")
```

### Thread-Safe UI Updates

The `run_ui()` method ensures UI operations execute on the correct thread:

```python
def run_ui(self, fn: Callable[[], None]) -> None:
    """
    Safely execute function in UI thread.
    Can be called from any thread, ensuring UI operations execute in correct thread.
    """
    # Implementation handles thread dispatching
```

### State-Based Layout Switching

The UI dynamically switches layouts based on current state:

- **INPUT**: Shows input widget only
- **TOOL_CALL**: Shows tool call widget + input widget
- **THINKING**: Shows thinking widget with streaming content

## 9. Component Interaction

```
User Input
    ↓
InputWidget → USER_INPUT_RECEIVED event
    ↓
EventBus → UIEventHandler
    ↓
ConsoleUI state change
    ↓
Layout switch → Component update
```

## 10. Future Extensibility

The abstract `BaseUI` interface allows for future implementations:

- Web UI (Flask/FastAPI + React)
- Desktop UI (Tkinter/PyQt)
- Mobile UI (Kivy)
- Terminal UI variants (different terminal libraries)

All implementations would follow the same interface contract, ensuring consistent behavior across platforms.

