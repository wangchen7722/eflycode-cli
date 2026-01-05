from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator

from eflycode.core.llm.protocol import ChatCompletion, ChatCompletionChunk, LLMRequest


@dataclass(frozen=True)
class ProviderCapabilities:
    supports_streaming: bool = True
    supports_tools: bool = True

class LLMProvider(ABC):
    
    @property
    def capabilities(self) -> ProviderCapabilities:
        raise NotImplementedError

    @abstractmethod
    def call(self, request: LLMRequest) -> ChatCompletion:
        raise NotImplementedError

    @abstractmethod
    def stream(self, request: LLMRequest) -> Iterator[ChatCompletionChunk]:
        raise NotImplementedError
