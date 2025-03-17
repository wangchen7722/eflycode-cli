import json
import logging
from typing import Dict, Any, List, Optional, Generator, Literal, Union, overload

import httpx

from echo.llms.llm_engine import LLMEngine, LLMConfig, build_generate_config
from echo.llms.schema import ChatCompletion, ChatCompletionChunk
from echo.utils.logger import get_logger

logger: logging.Logger = get_logger("openai_engine")


class OpenAIEngine(LLMEngine):
    """OpenAI Compatible API引擎"""

    def __init__(
            self,
            llm_config: LLMConfig,
            headers: Optional[Dict[str, str]] = None,
            **kwargs: Dict[str, Any]
    ):
        """初始化OpenAI Compatible API引擎
        
        Args:
            llm_config: LLM配置
            headers: 请求头
            **kwargs: 其他参数
        """
        super().__init__(llm_config, headers, **kwargs)
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                **(self.headers or {})
            },
            timeout=30.0
        )

    def _generate_non_stream(
            self,
            messages: List[Dict[str, str]],
            request_data: Dict[str, Any]
    ) -> ChatCompletion:
        """非流式生成回复

        Args:
            messages: 消息列表
            request_data: 请求数据

        Returns:
            ChatCompletion对象
        """
        response = self._client.post(
            "/v1/chat/completions",
            json=request_data
        )
        response.raise_for_status()
        return ChatCompletion.model_validate(response.json())

    def _generate_stream(
            self,
            messages: List[Dict[str, str]],
            request_data: Dict[str, Any]
    ) -> Generator[ChatCompletionChunk, None, None]:
        """流式生成回复

        Args:
            messages: 消息列表
            request_data: 请求数据

        Returns:
            ChatCompletionChunk生成器
        """
        with self._client.stream(
                "POST",
                "/v1/chat/completions",
                json=request_data
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    chunk_data = json.loads(data)
                    yield ChatCompletionChunk.model_validate(chunk_data)

    @overload
    def generate(
        self,
        messages: List[Dict[str, str]],
        stream: Literal[False] = False,
        **kwargs: Dict[str, Any]
    ) -> ChatCompletion:
        ...

    @overload
    def generate(
            self,
            messages: List[Dict[str, str]],
            stream: Literal[True],
            **kwargs: Dict[str, Any]
    ) -> Generator[ChatCompletionChunk, None, None]:
        ...

    def generate(
            self,
            messages: List[Dict[str, str]],
            stream: bool = False,
            **kwargs: Dict[str, Any]
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        """生成回复

        Args:
            messages: 消息列表
            stream: 是否使用流式生成
            **kwargs: 其他参数

        Returns:
            如果stream=False，返回ChatCompletion对象；如果stream=True，返回ChatCompletionChunk生成器
        """
        generate_config = build_generate_config(self.llm_config, **kwargs)
        request_data = {
            "model": self.model,
            "messages": messages,
            **generate_config
        }

        if not stream:
            return self._generate_non_stream(messages, request_data)
        else:
            return self._generate_stream(messages, request_data)
