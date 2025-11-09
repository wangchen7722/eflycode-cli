"""
配置环境管理器

提供统一的配置访问接口，支持热重载
"""

from typing import Dict, Any, Optional, Callable, List
from threading import Lock

from eflycode.env.config_loader import ConfigLoader
from eflycode.util.file_watcher import FileWatcher
from eflycode.util.logger import configure_logging, logger
from eflycode.schema.config import AppConfig, ModelConfig, LLMConfig, ModelEntry, RuntimeConfig


def get_nested_value(config: Dict[str, Any], key: str) -> Any:
    """
    获取嵌套配置值
    
    Args:
        config: 配置字典
        key: 配置键，支持点分隔
        
    Returns:
        配置值，不存在时返回None
    """
    keys = key.split(".")
    value = config
    
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return None
    
    return value

def set_nested_value(config: Dict[str, Any], key: str, value: Any) -> None:
    """
    设置嵌套配置值
    
    Args:
        config: 配置字典
        key: 配置键，支持点分隔
        value: 配置值
    """
    keys = key.split(".")
    current = config
    
    for k in keys[:-1]:
        if k not in current or not isinstance(current[k], dict):
            current[k] = {}
        current = current[k]
    
    current[keys[-1]] = value

class Environment:
    """配置环境管理器"""
    
    _instance: Optional["Environment"] = None
    _lock = Lock()
    
    def __init__(self):
        self._config_loader = ConfigLoader()
        self._file_watcher = FileWatcher()
        self._change_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._app_config: Optional[AppConfig] = None
        self._runtime_config: Optional[RuntimeConfig] = None
        
        # 初始化状态
        self._initialized = False
        self.reload()
        self._initialized = True
        
    def __new__(cls, *args, **kwargs) -> "Environment":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> "Environment":
        """
        获取Environment单例实例
        
        Returns:
            Environment实例
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def reload(self) -> None:
        """
        重新加载所有配置
        """
        self._app_config = self._config_loader.load_config()
        self._runtime_config = self._config_loader.get_runtime_config()
        self._initialize_logging()
        self._setup_file_watching()

    def save_workspace_settings(self) -> None:
        """
        保存当前工作区配置
        """
        if self._app_config is None:
            return
        
        # 保存工作区配置
        self._config_loader.save_workspace_settings(self._app_config.model_dump())
    
    def _setup_file_watching(self) -> None:
        """设置文件监听"""
        paths = self._config_loader.get_config_paths()
        # 监听全局配置文件
        self._file_watcher.add_file(paths["global"], self._on_config_file_changed)
        # 监听工作区配置文件
        self._file_watcher.add_file(paths["workspace"], self._on_config_file_changed)
        # 开始监听
        self._file_watcher.start()
    
    def _on_config_file_changed(self, file_path: str) -> None:
        """配置文件变化回调"""
        self.reload()

    def _initialize_logging(self) -> None:
        """
        初始化日志配置
        
        在配置加载完成后配置日志系统
        """
        try:
            if self._app_config is None:
                logger.error("应用配置为空，无法初始化日志配置")
                return
            configure_logging(self._app_config.logging)
        except Exception as e:
            logger.exception(f"日志配置初始化失败: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键，支持点分隔的嵌套键, 如 "logging.level"
            default: 默认值
            
        Returns:
            配置值
        """
        return get_nested_value(self._app_config.model_dump(), key) or default
    
    def set(self, key: str, value: Any) -> None:
        """
        设置运行时配置值
        
        Args:
            key: 配置键，支持点分隔的嵌套键
            value: 配置值
        """
        set_nested_value(self._app_config.model_dump(), key, value)
        self.save_workspace_settings()
    
    def get_model_config(self) -> ModelConfig:
        """
        获取模型配置
        
        Returns:
            模型配置对象
        """
        return self._app_config.model

    def get_llm_config(self) -> LLMConfig:
        """
        获取LLM配置

        Returns:
            LLM配置对象
        """
        # 从 model config 中找到默认的模型
        model_config = self.get_model_config()
        # 从 model entries 中找到对应的配置
        default_model = model_config.default
        model_entries: List[ModelEntry] = model_config.entries or []
        llm_entry = None
        for entry in model_entries:
            if entry.model == default_model:
                llm_entry = entry
                break
        if llm_entry is None:
            raise ValueError(f"未找到默认模型 '{default_model}' 的配置项")
        return LLMConfig(**llm_entry.model_dump())
    
    def get_runtime_config(self) -> RuntimeConfig:
        """
        获取运行时配置
        
        Returns:
            运行时配置对象
        """
        if self._runtime_config is None:
            self._runtime_config = self._config_loader.get_runtime_config()
        return self._runtime_config
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self._file_watcher.stop()
    
    def __del__(self):
        """析构函数"""
        if hasattr(self, "_file_watcher"):
            self._file_watcher.stop()