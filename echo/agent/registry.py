from typing import Dict, Type, Optional, Any
from functools import wraps
import inspect

from echo.llm.llm_engine import LLMEngine
from echo.agent.core.agent import Agent


class AgentRegistry:
    """Agent注册中心"""
    
    _instance: Optional["AgentRegistry"] = None
    _agents: Dict[str, Type[Agent]] = {}
    
    def __new__(cls) -> "AgentRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def register(cls, name: Optional[str] = None) -> callable:
        """注册Agent的装饰器
        
        Args:
            name: Agent名称，如果不提供则使用类的ROLE属性或类名
            
        Returns:
            装饰器函数
            
        Raises:
            ValueError: 当Agent名称已存在时
        """
        def decorator(agent_class: Type[Agent]) -> Type[Agent]:
            # 确定Agent名称
            agent_name = name
            if agent_name is None:
                agent_name = getattr(agent_class, "ROLE", agent_class.__name__.lower())
            
            # 检查是否已存在相同名称的Agent
            if agent_name in cls._agents:
                existing_class = cls._agents[agent_name]
                raise ValueError(
                    f"Agent名称 '{agent_name}' 已存在，已注册的类: {existing_class.__name__}，"
                    f"尝试注册的类: {agent_class.__name__}"
                )
            
            # 验证是否为Agent的子类
            if not issubclass(agent_class, Agent):
                raise TypeError(f"类 {agent_class.__name__} 必须继承自 Agent")
            
            # 注册Agent
            cls._agents[agent_name] = agent_class
            
            # 为类添加注册信息
            agent_class._registry_name = agent_name
            
            return agent_class
        
        return decorator
    
    @classmethod
    def get_agent_class(cls, name: str) -> Type[Agent]:
        """根据名称获取Agent类
        
        Args:
            name: Agent名称
            
        Returns:
            Agent类
            
        Raises:
            KeyError: 当Agent名称不存在时
        """
        if name not in cls._agents:
            available_agents = list(cls._agents.keys())
            raise KeyError(
                f"未找到名称为 '{name}' 的Agent。可用的Agent: {available_agents}"
            )
        return cls._agents[name]
    
    @classmethod
    def list_agents(cls) -> Dict[str, Type[Agent]]:
        """列出所有已注册的Agent
        
        Returns:
            包含所有已注册Agent的字典
        """
        return cls._agents.copy()
    
    @classmethod
    def create_agent(
        cls, 
        agent_type: str, 
        llm_engine: LLMEngine, 
        **kwargs: Any
    ) -> Agent:
        """创建指定类型的Agent实例
        
        Args:
            agent_type: Agent类型名称
            llm_engine: 语言模型引擎
            **kwargs: 传递给Agent构造函数的其他参数
            
        Returns:
            Agent实例
            
        Raises:
            KeyError: 当Agent类型不存在时
        """
        agent_class = cls.get_agent_class(agent_type)
        return agent_class(llm_engine=llm_engine, **kwargs)


# 创建全局注册中心实例
_registry = AgentRegistry()

# 导出装饰器和工厂函数
register_agent = _registry.register
create_agent = _registry.create_agent
list_agents = _registry.list_agents
get_agent_class = _registry.get_agent_class