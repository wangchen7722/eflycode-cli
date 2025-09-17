from typing import Dict, Optional, Any

import httpx

from echo.llm.llm_engine import LLMConfig, LLMEngine
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

    def _generate_request_data(self, request: LLMRequest) -> Dict[str, Any]:
        """生成请求数据
        
        Args:
            request: LLM请求
        
        Returns:
            包含请求数据的字典
        """
        request_data = {
            "model": request.model,
            "messages": [message.model_dump() for message in request.messages],
            **request.generate_config
        }
        if request.context.capability.supports_native_tool_call and request.tools:
            request_data["tools"] = [
                tool.model_dump() for tool in request.tools
            ]
            request_data["tool_choice"] = request.tool_choice
        return request_data

    def do_call(
        self,
        request: LLMRequest,
    ) -> LLMCallResponse:
        """非流式生成回复

        Args:
            request: LLM请求

        Returns:
            LLMCallResponse对象
        """
        
        request_data = self._generate_request_data(request)
        request_data["stream"] = False
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
        request_data = self._generate_request_data(request)
        request_data["stream"] = True
        response = self._client.post(
            "/chat/completions",
            json=request_data
        )
        response.raise_for_status()
        return LLMStreamResponse(**response.json())

