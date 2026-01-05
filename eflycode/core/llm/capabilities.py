
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelCapabilities:
    supports_streaming: bool = True
    supports_tools: bool = True
    supports_vision: bool = False
    supports_json_schema: bool = False