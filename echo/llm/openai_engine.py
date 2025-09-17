from typing import Dict, Optional

import httpx

from echo.util.logger import logger
from echo.llm.llm_engine import LLMConfig, LLMEngine, build_generate_config
from echo.schema.llm import LLMCallResponse, LLMStreamResponse, LLMRequest


class OpenAIEngine(LLMEngine):
    """OpenAI Compatible API引擎"""

    def __init__(
        self,
        llm_config: LLMConfig,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
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

    def do_call(
        self,
        request: LLMRequest,
    ) -> LLMCallResponse:
        """非流式生成回复

        Args:
            messages: 消息列表
            request_data: 请求数据

        Returns:
            LLMCallResponse对象
        """
        generate_config = build_generate_config(self.llm_config, **request.generate_config)
        request_data = {
            "model": self.model,
            "messages": [message.model_dump() for message in request.messages],
            "stream": False,
            **generate_config,
        }

        response = self._client.post(
            "/chat/completions",
            json=request_data
        )
        response.raise_for_status()
        return LLMCallResponse(**response.json())

    def do_stream(self, request: LLMRequest) -> LLMStreamResponse:
        """流式生成回复

        Args:
            request: LLM请求

        Returns:
            LLMStreamResponse对象
        """
        generate_config = build_generate_config(self.llm_config, **request.generate_config)
        request_data = {
            "model": self.model,
            "messages": [message.model_dump() for message in request.messages],
            "stream": True,
            **generate_config,
        }

        response = self._client.post(
            "/chat/completions",
            json=request_data
        )
        response.raise_for_status()
        return LLMStreamResponse(**response.json())

