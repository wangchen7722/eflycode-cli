from abc import ABC, abstractmethod
from typing import Generator, Optional, Sequence, Dict, Any, List
from echo.tool.base_tool import BaseTool
from echo.llm.schema import ChatCompletionChunk
from echo.parser.schema import AgentResponseChunk


class ResponseParser(ABC):
    """
    抽象流式响应解析器基类
    
    参考 vllm 项目的工具解析器设计模式，提供统一的流式响应解析接口。
    不同的解析策略可以继承此类并实现具体的解析逻辑。
    """
    
    def __init__(self, tools: Sequence[BaseTool]):
        """
        初始化解析器
        
        Args:
            tools: 可用的工具列表
        """
        self.tools = tools
        self.tool_map = {tool.name: tool for tool in tools}
    
    @abstractmethod
    def parse_stream(
        self, 
        chat_completion_chunk_stream: Generator[ChatCompletionChunk, None, None]
    ) -> Generator[AgentResponseChunk, None, None]:
        """
        解析流式响应
        
        Args:
            chat_completion_chunk_stream: 聊天完成块的流式生成器
            
        Yields:
            AgentResponseChunk: 解析后的响应块
        """
        pass
    
    def get_tool_by_name(self, name: str) -> Optional[BaseTool]:
        """
        根据名称获取工具
        
        Args:
            name: 工具名称
            
        Returns:
            对应的工具实例，如果不存在则返回None
        """
        return self.tool_map.get(name)
    
    def get_tool_parameters(self, tool_name: str) -> List[str]:
        """
        获取工具的参数列表
        
        Args:
            tool_name: 工具名称
            
        Returns:
            工具参数名称列表
        """
        tool = self.get_tool_by_name(tool_name)
        return list(tool.parameters.keys()) if tool else []
    
    def is_valid_tool(self, tool_name: str) -> bool:
        """
        检查是否为有效的工具名称
        
        Args:
            tool_name: 工具名称
            
        Returns:
            是否为有效工具
        """
        return tool_name in self.tool_map
    
    def is_valid_parameter(self, tool_name: str, param_name: str) -> bool:
        """
        检查是否为工具的有效参数
        
        Args:
            tool_name: 工具名称
            param_name: 参数名称
            
        Returns:
            是否为有效参数
        """
        tool = self.get_tool_by_name(tool_name)
        return param_name in tool.parameters if tool else False