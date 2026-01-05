from dataclasses import dataclass
from typing import Optional
from rich.live import Live

@dataclass
class _StreamingState:
    live: Optional[Live] = None
    buffer: str = ""
    

# class Renderer: