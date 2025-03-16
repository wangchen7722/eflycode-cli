import os
import time
import json
import logging
from typing import Dict, Any, List, Optional, Generator

from openai import OpenAI

from echo.llms.llm_engine import LLMEngine, LLMConfig, build_generate_config
from echo.llms.schema import ChatCompletion, ChatCompletionChunk
from echo.utils.logger import get_logger

logger: logging.Logger = get_logger("openai_engine")


class OpenAIEngine(LLMEngine):
    """OpenAI LLM引擎实现"""

    def __init__(
            self,
            llm_config: LLMConfig,
            headers: Optional[Dict[str, str]] = None,
            **kwargs: Dict[str, Any]
    ):
        """初始化OpenAI引擎
        
        Args:
            llm_config: LLM配置
            headers: 请求头
            **kwargs: 其他参数
        """
        super().__init__(llm_config, headers, **kwargs)
        self._client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            max_retries=3,
            timeout=30
        )

    def generate(self, messages: List[Dict[str, str]], **kwargs: Dict[str, Any]) -> ChatCompletion | Generator[
        ChatCompletionChunk, None, None]:
        """生成回复

        Args:
            messages: 消息列表
            **kwargs: 其他参数

        Returns:
            如果stream=False，返回ChatCompletion对象；如果stream=True，返回ChatCompletionChunk生成器
        """
        generate_config = build_generate_config(self.llm_config, **kwargs)
        stream_flag = generate_config.get("stream", False)

        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            **generate_config
        )

        if stream_flag:
            for chunk in response:
                yield ChatCompletionChunk.model_validate(chunk.model_dump())
        return ChatCompletion.model_validate(response.model_dump())
