from abc import abstractmethod
from typing import Any, Dict, Optional, List

from echo.schema.llm import (
    LLMConfig,
    LLMRequest,
    LLMStreamResponse,
    LLMCallResponse,
    LLMCapability,
    LLMRequestContext,
    LLMPrompt
)
from echo.llm.advisor import Advisor, AdvisorChain
from echo.llm.advisors.tool_call_advisor import ToolCallAdvisor


ALLOWED_GENERATE_CONFIG_KEYS = [
    "model",
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


def build_generate_config(llm_config: LLMConfig, generate_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """构建生成配置

    Args:
        llm_config: LLM配置
        **kwargs: 其他参数

    Returns:
        Dict[str, Any]: 生成配置字典
    """
    config = {}
    llm_config_kwargs = llm_config.model_dump()
    for key in llm_config_kwargs:
        if key in ALLOWED_GENERATE_CONFIG_KEYS:
            config[key] = llm_config_kwargs[key]
    if generate_config:
        for key in generate_config:
            if key in ALLOWED_GENERATE_CONFIG_KEYS:
                config[key] = generate_config[key]
    return config


class LLMEngine:
    """大语言模型引擎，负责处理与LLM的交互"""

    def __init__(
        self,
        llm_config: LLMConfig,
        headers: Optional[Dict[str, str]] = None,
        advisors: Optional[List[Advisor]] = None,
        **kwargs,
    ):
        """初始化LLM引擎

        Args:
            llm_config: LLM配置
            headers: 请求头
            **kwargs: 其他参数
        """
        self.llm_config = llm_config
        self.model = self.llm_config.model
        self.base_url = self.llm_config.base_url
        self.api_key = self.llm_config.api_key
        self.headers = headers or {}
        self._advisor_chain = AdvisorChain(advisors or [])

    @abstractmethod
    def do_call(self, request: LLMRequest) -> LLMCallResponse:
        """调用模型

        Args:
            request: LLM请求

        Returns:
            LLMCallResponse: 调用响应
        """
        raise NotImplementedError

    @abstractmethod
    def do_stream(self, request: LLMRequest) -> LLMStreamResponse:
        """调用模型并返回流式响应

        Args:
            request: LLM请求

        Returns:
            LLMStreamResponse: 流式响应
        """
        raise NotImplementedError

    def _ensure_request_context(self, prompt: LLMPrompt) -> LLMRequest:
        capability = LLMCapability(
            supports_native_tool_call=self.llm_config.supports_native_tool_call
        )
        request = LLMRequest(
            model=self.model,
            messages=prompt.messages,
            tools=prompt.tools,
            tool_choice=prompt.tool_choice,
            generate_config=build_generate_config(self.llm_config, prompt.generate_config),
            context=LLMRequestContext(capability=capability)
        )
        return request


    def call(self, prompt: LLMPrompt) -> LLMCallResponse:
        """带 AdvisorChain 的非流式调用"""
        request = self._ensure_request_context(prompt)
        if prompt.tools:
            self._advisor_chain.advisors.insert(0, ToolCallAdvisor(tools=prompt.tools))
        wrapped = self._advisor_chain.wrap_call(self.do_call)
        return wrapped(request)

    def stream(self, prompt: LLMPrompt) -> LLMStreamResponse:
        """带 AdvisorChain 的流式调用"""
        request = self._ensure_request_context(prompt)
        if prompt.tools:
            self._advisor_chain.advisors.insert(0, ToolCallAdvisor(tools=prompt.tools))
        wrapped = self._advisor_chain.wrap_stream(self.do_stream)
        return wrapped(request)
