from dataclasses import dataclass

@dataclass
class _StreamingState:
    buffer: str = ""
    

# class Renderer: