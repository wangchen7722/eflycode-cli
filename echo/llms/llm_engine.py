from typing import Dict, Any, List, Optional, TypedDict
import os

class LLMConfig(TypedDict):
    """LLM配置类型定义"""
    base_url: Optional[str]
    api_key: Optional[str]
    model: Optional[str]
    temperature: Optional[float]
    max_tokens: Optional[int]

class LLMEngine:
    """大语言模型引擎，负责处理与LLM的交互"""
    
    ALLOW_GENERATE_CONFIG_KEYS = [
        "stream"
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
    
    def __init__(
        self,
        llm_config: Optional[LLMConfig] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs: Dict[str, Any]
    ):
        """初始化LLM引擎
        
        Args:
            llm_config: LLM配置
            headers: 请求头
            **kwargs: 其他参数
        """
        self.llm_config = llm_config or {}
        self.base_url = self.llm_config.get('base_url') or os.getenv('ECHO_BASE_URL')
        self.api_key = self.llm_config.get('api_key') or os.getenv('ECHO_API_KEY')
        self.headers = headers or {}
        
        self.generate_config = self._build_generate_config()
        
        # 设置默认的模型参数
        self.model = self.llm_config.get('model')
        self.temperature = self.llm_config.get('temperature')
        self.max_tokens = self.llm_config.get('max_tokens')
    
    def _build_generate_config(self) -> Dict[str, Any]:
        """构建生成配置
        
        Returns:
            Dict[str, Any]: 生成配置字典
        """
        config = {}
        for key in self.ALLOW_GENERATE_CONFIG_KEYS:
            if key in self.llm_config:
                config[key] = self.llm_config[key]
        return config
    
    def generate(self, messages: List[Dict[str, str]], **kwargs: Dict[str, Any]) -> str:
        """生成LLM响应
        
        Args:
            messages: 消息列表，每个消息是一个字典，包含role和content字段
            **kwargs: 其他参数
            
        Returns:
            str: LLM的响应文本
        """
        raise NotImplementedError