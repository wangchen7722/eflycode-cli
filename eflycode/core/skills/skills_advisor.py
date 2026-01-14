"""Skills Advisor

在系统提示词中注入 <available_skills>
"""

from typing import List, Optional

from eflycode.core.agent.base import BaseAgent
from eflycode.core.config.models import Config
from eflycode.core.llm.advisor import Advisor
from eflycode.core.llm.protocol import LLMRequest, Message
from eflycode.core.skills.manager import SkillsManager
from eflycode.core.utils.logger import logger


class SkillsAdvisor(Advisor):
    """Skills Advisor，在系统提示词中注入可用技能列表"""

    def __init__(self, agent: Optional[BaseAgent] = None, config: Optional[Config] = None):
        """初始化 Skills Advisor

        Args:
            agent: Agent 实例（可以为 None，稍后设置）
            config: 配置对象
        """
        self._agent = agent
        self._config = config
        self.manager: SkillsManager = SkillsManager.get_instance()

    @property
    def agent(self) -> BaseAgent:
        """获取 Agent 实例"""
        if self._agent is None:
            raise RuntimeError("SkillsAdvisor.agent 未被设置")
        return self._agent

    @agent.setter
    def agent(self, value: BaseAgent) -> None:
        """设置 Agent 实例"""
        self._agent = value

    @property
    def config(self) -> Config:
        """获取配置对象"""
        if self._config is None:
            raise RuntimeError("SkillsAdvisor.config 未被设置")
        return self._config

    def _build_available_skills_block(self) -> str:
        """构建 <available_skills> XML 块

        Returns:
            str: <available_skills> XML 块
        """
        available_skills = self.manager.get_available_skills_for_prompt()

        if not available_skills:
            return ""

        # 构建 XML 块
        lines = ["<available_skills>"]
        for skill in available_skills:
            lines.append(f"  <skill>")
            lines.append(f"    <name>{skill['name']}</name>")
            lines.append(f"    <description>{skill['description']}</description>")
            lines.append(f"    <location>{skill['location']}</location>")
            lines.append(f"  </skill>")
        lines.append("</available_skills>")

        return "\n".join(lines)

    def _add_available_skills(self, request: LLMRequest) -> LLMRequest:
        """添加可用技能到请求

        Args:
            request: LLM 请求

        Returns:
            LLMRequest: 修改后的请求
        """
        # 检查是否启用了 skills 功能
        if not self.config.skills_enabled:
            logger.debug("Skills 功能未启用，跳过添加 <available_skills>")
            return request

        # 获取可用技能块
        skills_block = self._build_available_skills_block()

        if not skills_block:
            logger.debug("没有可用的技能，跳过添加 <available_skills>")
            return request

        # 查找现有的 system message
        system_message = None
        system_index = -1

        for i, msg in enumerate(request.messages):
            if msg.role == "system":
                system_message = msg
                system_index = i
                break

        # 构建要添加的内容
        addition = "\n\n" + skills_block + "\n\n"
        addition += "当任务匹配某个技能时，请使用 activate_skill 工具激活该技能。\n"
        addition += "激活后，请严格优先遵循 <activated_skill> 中的指令。"

        if system_message:
            # 在现有 system message 末尾添加
            if isinstance(system_message.content, str):
                request.messages[system_index] = Message(
                    role="system",
                    content=system_message.content + addition,
                )
                logger.debug(f"在现有系统提示词末尾添加 <available_skills>")
        else:
            # 创建新的 system message
            request.messages.insert(
                0, Message(role="system", content=skills_block + addition)
            )
            logger.debug(f"创建新的系统提示词并添加 <available_skills>")

        return request

    def before_call(self, request: LLMRequest) -> LLMRequest:
        """在请求发送前添加可用技能

        Args:
            request: LLM 请求

        Returns:
            LLMRequest: 修改后的请求
        """
        return self._add_available_skills(request)

    def before_stream(self, request: LLMRequest) -> LLMRequest:
        """在流式请求发送前添加可用技能

        Args:
            request: LLM 请求

        Returns:
            LLMRequest: 修改后的请求
        """
        return self._add_available_skills(request)
