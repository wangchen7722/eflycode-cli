"""Agent 注册表

负责管理可用的 Agent 类型
"""

from typing import Dict, Optional, Type

from eflycode.core.agent.base import BaseAgent
from eflycode.core.utils.logger import logger


class AgentRegistry:
    """Agent 注册表单例"""

    _instance: Optional["AgentRegistry"] = None

    def __init__(self):
        """初始化注册表"""
        self._agents: Dict[str, Type[BaseAgent]] = {}

    @classmethod
    def get_instance(cls) -> "AgentRegistry":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, name: str, agent_cls: Type[BaseAgent]) -> None:
        """注册 Agent 类型"""
        if not issubclass(agent_cls, BaseAgent):
            raise ValueError("agent_cls 必须继承 BaseAgent")
        self._agents[name] = agent_cls
        logger.debug(f"注册 Agent: name={name}, cls={agent_cls.__name__}")

    def get(self, name: str) -> Optional[Type[BaseAgent]]:
        """获取 Agent 类型"""
        return self._agents.get(name)

    def list_agents(self) -> Dict[str, Type[BaseAgent]]:
        """获取所有注册的 Agent 类型"""
        return dict(self._agents)

    def clear(self) -> None:
        """清空注册表（主要用于测试）"""
        agent_count = len(self._agents)
        self._agents.clear()
        logger.info(f"清空所有 Agent 注册: cleared={agent_count}")
