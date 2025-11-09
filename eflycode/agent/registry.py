import re
import importlib
import pkgutil
from typing import Dict, Type, Optional, Any

from eflycode.llm.llm_engine import LLMEngine
from eflycode.agent.core.agent import ConversationAgent


def camel_to_snake(name: str) -> str:
    """将驼峰命名转为下划线命名"""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


class AgentRegistry:
    """Agent注册中心"""
    
    _instance: Optional["AgentRegistry"] = None
    
    def __init__(self) -> None:
        if not hasattr(self, "_initialized"):
            self._agents: Dict[str, Type[ConversationAgent]] = {}
            self._scanned_packages: set[str] = set()
            self.scan_agents("eflycode.agent")
            self._initialized = True
    
    def __new__(cls) -> "AgentRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def scan_agents(self, package_name: str) -> None:
        """扫描指定包中的所有 Agent 类
        
        Args:
            package_name: 包名，例如 'eflycode.agent'
        """
        if package_name in self._scanned_packages:
            return
        package = importlib.import_module(package_name)

        # 如果单文件模块, 直接扫描
        if not hasattr(package, "__path__"):
            self._scan_module(package, ConversationAgent)
            return

        # 否则递归扫描包下所有模块
        for _, name, is_pkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            mod = importlib.import_module(name)
            self._scan_module(mod, ConversationAgent)

        self._scanned_packages.add(package_name)
    
    def _scan_module(self, module: Any, base_class: Type[ConversationAgent]) -> None:
        """扫描模块中的Agent类
        
        Args:
            module: 模块对象
            base_class: 基类，用于筛选Agent类
        """
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and issubclass(obj, base_class) and obj != base_class:
                role = getattr(obj, "ROLE", None)
                if role is None:
                    agent_name = camel_to_snake(name)
                else:
                    agent_name = role
                self.register(agent_name, obj)
    
    def register(self, name: str, clazz: Type[ConversationAgent], overwrite: bool = False) -> None:
        """注册Agent类
        
        Args:
            name: Agent名称
            clazz: Agent类
            overwrite: 是否覆盖已存在的注册, 默认为 False
            
        Raises:
            ValueError: 当 Agent 名称已存在时
        """
        # 如果 overwrite 为 False, 且名称已存在, 则抛出异常
        if not overwrite and name in self._agents:
            raise ValueError(f"Agent 名称 '{name}' 已存在，无法注册")
        
        self._agents[name] = clazz

    def get_agent_class(self, name: str) -> Type[ConversationAgent]:
        """根据名称获取Agent类
        
        Args:
            name: Agent名称
            
        Returns:
            Agent类
            
        Raises:
            KeyError: 当Agent名称不存在时
        """
        if name not in self._agents:
            available_agents = list(self._agents.keys())
            raise KeyError(
                f"未找到名称为 '{name}' 的Agent。可用的Agent: {available_agents}"
            )
        return self._agents[name]
    
    def list_agents(self) -> Dict[str, Type[ConversationAgent]]:
        """列出所有已注册的Agent
        
        Returns:
            包含所有已注册Agent的字典
        """
        return self._agents.copy()
    
    def create_agent(
        self, 
        agent_type: str, 
        llm_engine: LLMEngine, 
        **kwargs: Any
    ) -> ConversationAgent:
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
        agent_class = self.get_agent_class(agent_type)
        return agent_class(llm_engine=llm_engine, **kwargs)
