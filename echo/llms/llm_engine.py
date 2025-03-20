import logging
import os
from typing import Dict, Any, List, NotRequired, Optional, Generator, Literal, overload
from typing_extensions import TypedDict

from echo.llms.schema import Message, ChatCompletion, ChatCompletionChunk
from echo.utils.logger import get_logger


class LLMConfig(TypedDict):
    """LLM配置类型定义"""
    model: str
    base_url: str
    api_key: str
    temperature: NotRequired[Optional[float]]
    max_tokens: NotRequired[Optional[int]]


logger: logging.Logger = get_logger(os.path.splitext(os.path.basename(__file__))[0])

ALLOWED_GENERATE_CONFIG_KEYS = [
    "max_tokens",
    "frequency_penalty",
    "presence_penalty",
    "stop",
    "temperature",
    "top_p",
    "tools",
    "tool_choice",
    "logprobs",
]


def build_generate_config(
    llm_config: LLMConfig,
    **kwargs
) -> Dict[str, Any]:
    """构建生成配置

    Args:
        llm_config: LLM配置
        **kwargs: 其他参数

    Returns:
        Dict[str, Any]: 生成配置字典
    """
    config = {}
    for key in llm_config:
        if key in ALLOWED_GENERATE_CONFIG_KEYS:
            config[key] = llm_config[key]
    if kwargs:
        for key in kwargs:
            if key in ALLOWED_GENERATE_CONFIG_KEYS:
                config[key] = kwargs[key]
    return config


class LLMEngine:
    """大语言模型引擎，负责处理与LLM的交互"""

    def __init__(
            self,
            llm_config: LLMConfig,
            headers: Optional[Dict[str, str]] = None,
            **kwargs
    ):
        """初始化LLM引擎
        
        Args:
            llm_config: LLM配置
            headers: 请求头
            **kwargs: 其他参数
        """
        self.llm_config = llm_config
        if "model" not in self.llm_config:
            raise ValueError("LLM配置中缺少model字段")
        if "base_url" not in self.llm_config:
            raise ValueError("LLM配置中缺少base_url字段")
        if "api_key" not in self.llm_config:
            raise ValueError("LLM配置中缺少api_key字段")
        self.model = self.llm_config.get("model")
        self.base_url = self.llm_config.get("base_url")
        self.api_key = self.llm_config.get("api_key")
        self.headers = headers or {}

    @overload
    def generate(
        self,
        messages: List[Message],
        stream: Literal[False] = False,
        **kwargs
    ) -> ChatCompletion:
        ...

    @overload
    def generate(
            self,
            messages: List[Message],
            stream: Literal[True],
            **kwargs
    ) -> Generator[ChatCompletionChunk, None, None]:
        ...

    def generate(
        self, 
        messages: List[Message], 
        stream: bool = True,
        **kwargs
    ) -> ChatCompletion | Generator[
        ChatCompletionChunk, None, None]:
        """生成LLM响应
        
        Args:
            messages: 消息列表，每个消息是一个字典，包含role和content字段
            stream: 是否流式响应
            **kwargs: 其他参数
            
        Returns:
            ChatCompletion | Generator[ChatCompletionChunk, None, None]: LLM响应
        """
        raise NotImplementedError