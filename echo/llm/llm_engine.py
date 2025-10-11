from abc import abstractmethod
from typing import Any, Dict, Optional, List, Union
from echo.util.logger import logger

from echo.schema.llm import (
    LLMConfig,
    LLMRequest,
    LLMStreamResponse,
    LLMCallResponse,
    LLMCapability,
    LLMRequestContext,
    LLMPrompt
)
from echo.llm.advisor import Advisor, AdvisorChain, AdvisorRegistry


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


def build_generate_config(
    llm_config: LLMConfig, generate_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
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
        advisors: Optional[List[str]] = None,
        **kwargs,
    ):
        """初始化LLM引擎

        Args:
            llm_config: LLM配置
            headers: 请求头
            advisors: Advisor名称列表，用于从AdvisorRegistry获取Advisor实例
            **kwargs: 其他参数
        """
        self.llm_config = llm_config
        self.model = self.llm_config.model
        self.base_url = self.llm_config.base_url
        self.api_key = self.llm_config.api_key
        self.headers = headers or {}

        # 处理advisors参数，支持字符串类型
        processed_advisors = []
        if advisors:
            for advisor in advisors:
                try:
                    advisor_class = AdvisorRegistry.get_advisor(advisor)
                    processed_advisors.append(advisor_class())
                except KeyError:
                    logger.warning(f"未找到名称为 '{advisor}' 的Advisor，已跳过")
                    continue

        self._advisor_chain = AdvisorChain(processed_advisors)

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
            generate_config=build_generate_config(
                self.llm_config, prompt.generate_config
            ),
            context=LLMRequestContext(capability=capability),
        )
        return request

    def call(self, prompt: LLMPrompt) -> LLMCallResponse:
        """带 AdvisorChain 的非流式调用"""
        request = self._ensure_request_context(prompt)
        if prompt.tools:
            # 从注册表获取ToolCallAdvisor类并实例化
            tool_call_advisor_class = AdvisorRegistry.get_advisor(
                "buildin_tool_call_advisor"
            )
            tool_call_advisor = tool_call_advisor_class()
            # 添加 advisor 到链中
            self._advisor_chain.add_advisor(tool_call_advisor)
        wrapped = self._advisor_chain.wrap_call(self.do_call)
        return wrapped(request)

    def stream(self, prompt: LLMPrompt) -> LLMStreamResponse:
        """带 AdvisorChain 的流式调用"""
        request = self._ensure_request_context(prompt)
        if prompt.tools:
            # 从注册表获取ToolCallAdvisor类并实例化
            tool_call_advisor_class = AdvisorRegistry.get_advisor(
                "buildin_tool_call_advisor"
            )
            tool_call_advisor = tool_call_advisor_class()
            # 添加 advisor 到链中
            self._advisor_chain.add_advisor(tool_call_advisor)
        wrapped = self._advisor_chain.wrap_stream(self.do_stream)
        return wrapped(request)

    def add_advisor(self, advisor: Advisor):
        """添加Advisor到引擎的AdvisorChain中

        Args:
            advisor: Advisor实例
        """
        self._advisor_chain.add_advisor(advisor)
