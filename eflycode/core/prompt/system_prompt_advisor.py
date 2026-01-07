"""系统提示词 Advisor

在每次请求时动态渲染并添加系统提示词
"""

from typing import Any, Dict

from eflycode.core.agent.base import BaseAgent
from eflycode.core.config.config_manager import ConfigManager
from eflycode.core.llm.advisor import Advisor
from eflycode.core.llm.protocol import LLMRequest, Message
from eflycode.core.prompt.loader import PromptLoader
from eflycode.core.utils.logger import logger


class SystemPromptAdvisor(Advisor):
    """系统提示词 Advisor，在请求前添加系统提示词"""

    def __init__(self, agent: BaseAgent):
        """初始化系统提示词 Advisor

        Args:
            agent: Agent 实例
        """
        self.agent = agent

    def _get_prompt_variables(self) -> Dict[str, Any]:
        """获取提示词变量

        从 ConfigManager 获取静态信息，从 agent 获取动态信息

        Returns:
            Dict[str, Any]: 变量字典
        """
        config_manager = ConfigManager.get_instance()

        # 从 ConfigManager 获取静态信息
        system_info = config_manager.get_system_info()
        workspace_info = config_manager.get_workspace_info()
        environment_info = config_manager.get_environment_info()

        # 从 agent 获取动态信息
        tools = []
        for tool_def in self.agent.get_available_tools():
            tools.append(
                {
                    "name": tool_def.function.name,
                    "description": tool_def.function.description,
                    "parameters": tool_def.function.parameters.model_dump(),
                }
            )

        context_strategy = "none"
        if self.agent.session.context_config:
            context_strategy = self.agent.session.context_config.strategy_type

        model_provider = "unknown"
        if hasattr(self.agent.provider, "__class__"):
            model_provider = self.agent.provider.__class__.__name__.replace("Provider", "").lower()

        return {
            "tools": tools,
            "system": system_info,
            "workspace": workspace_info,
            "model": {
                "name": self.agent.model_name,
                "provider": model_provider,
                "max_context_length": self.agent.max_context_length,
            },
            "context": {
                "strategy": context_strategy,
            },
            "environment": environment_info,
            "agent": {
                "name": self.agent.ROLE,
            },
        }

    def _add_system_prompt(self, request: LLMRequest) -> LLMRequest:
        """添加系统提示词到请求

        Args:
            request: LLM 请求

        Returns:
            LLMRequest: 修改后的请求
        """
        # 检查是否已有 system message
        if request.messages and request.messages[0].role == "system":
            # 已有 system message，不添加
            return request

        config_manager = ConfigManager.get_instance()
        prompt_loader = PromptLoader.get_instance()

        # 获取工作区目录
        workspace_dir = None
        if config_manager.config:
            workspace_dir = config_manager.config.workspace_dir

        # 加载模板
        template = prompt_loader.load_template(
            agent_role=self.agent.ROLE, workspace_dir=workspace_dir
        )

        if not template:
            # 没有找到模板，不添加 system message
            logger.debug("未找到系统提示词模板，跳过添加")
            return request

        # 获取变量
        variables = self._get_prompt_variables()

        # 渲染模板
        system_prompt = prompt_loader.render(template, variables)

        if not system_prompt:
            # 渲染失败，不添加 system message
            logger.warning("系统提示词渲染失败，跳过添加")
            return request

        # 在消息列表开头插入 system message
        system_message = Message(role="system", content=system_prompt)
        request.messages.insert(0, system_message)

        logger.debug(f"已添加系统提示词，长度: {len(system_prompt)} 字符")

        return request

    def before_call(self, request: LLMRequest) -> LLMRequest:
        """在请求发送前添加系统提示词

        Args:
            request: LLM 请求

        Returns:
            LLMRequest: 修改后的请求
        """
        return self._add_system_prompt(request)

    def before_stream(self, request: LLMRequest) -> LLMRequest:
        """在流式请求发送前添加系统提示词

        Args:
            request: LLM 请求

        Returns:
            LLMRequest: 修改后的请求
        """
        return self._add_system_prompt(request)

