"""
配置环境管理器

提供统一的配置访问接口，支持热重载
"""

from typing import Dict, Any, Optional, Callable, List
from threading import Lock
from copy import deepcopy

from eflycode.env.config_loader import ConfigLoader
from eflycode.util.file_watcher import FileWatcher
from eflycode.util.logger import configure_logging
from eflycode.schema.config import LoggingConfig, ModelConfig, LLMConfig, ModelEntry, WorkspaceConfig
from eflycode.llm.advisor import initialize_builtin_advisors


class Environment:
    """配置环境管理器（单例）"""
    
    _instance: Optional["Environment"] = None
    _lock = Lock()
    
    def __init__(self):
        if Environment._instance is not None:
            raise RuntimeError("Environment 是单例类，请使用 get_instance() 方法")
        
        self._config_loader = ConfigLoader()
        self._file_watcher = FileWatcher()
        self._config: Dict[str, Any] = {}
        self._runtime_config: Dict[str, Any] = {}
        self._change_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._initialized = False
        
        self._load_config()
        self._initialize_advisors()
        self._setup_file_watching()
        self._initialize_logging()
        self._initialize_workspace()
        self._initialized = True
    
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
    
    def _load_config(self) -> None:
        """加载配置"""
        try:
            self._config = self._config_loader.load_config()
        except Exception as e:
            print(f"加载配置失败: {e}")
            # 使用默认配置
            from .config_loader import DEFAULT_GLOBAL_CONFIG
            self._config = deepcopy(DEFAULT_GLOBAL_CONFIG)
    
    def _setup_file_watching(self) -> None:
        """设置文件监听"""
        paths = self._config_loader.get_config_paths()
        
        # 监听全局配置文件
        self._file_watcher.add_file(paths["global"], self._on_config_file_changed)
        
        # 监听项目配置文件
        self._file_watcher.add_file(paths["project"], self._on_config_file_changed)
        
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
            logging_config = self.get_logging_config()
            configure_logging(logging_config)
        except Exception as e:
            print(f"日志配置初始化失败: {e}")

    def _initialize_advisors(self) -> None:
        """初始化Advisor注册"""
        initialize_builtin_advisors()

    def _initialize_workspace(self) -> None:
        """
        初始化工作空间配置
        
        如果workspace配置为空，则设置当前工作目录
        """
        workspace_dir = self._config_loader.get_workspace_dir()
        self.set("workspace.work_dir", workspace_dir)

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键，支持点分隔的嵌套键（如 "logging.level"）
            default: 默认值
            
        Returns:
            配置值
        """
        # 优先从运行时配置获取
        value = self._get_nested_value(self._runtime_config, key)
        if value is not None:
            return value
        
        # 从主配置获取
        value = self._get_nested_value(self._config, key)
        return value if value is not None else default
    
    def set(self, key: str, value: Any) -> None:
        """
        设置运行时配置值
        
        Args:
            key: 配置键，支持点分隔的嵌套键
            value: 配置值
        """
        self._set_nested_value(self._runtime_config, key, value)
        self._notify_change()
    
    def update(self, config: Dict[str, Any]) -> None:
        """
        批量更新运行时配置
        
        Args:
            config: 配置字典
        """
        self._runtime_config.update(config)
        self._notify_change()
    
    def get_logging_config(self) -> LoggingConfig:
        """
        获取日志配置
        
        Returns:
            日志配置对象
        """
        logging_dict = self.get("logging", {})
        return LoggingConfig(**logging_dict)
    
    def get_model_config(self) -> ModelConfig:
        """
        获取模型配置
        
        Returns:
            模型配置对象
        """
        model_dict = self.get("model", {})
        return ModelConfig(**model_dict)

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

    def get_workspace_config(self) -> WorkspaceConfig:
        """
        获取工作空间配置
        
        Returns:
            工作空间配置对象
        """
        workspace_dict = self.get("workspace", {})
        return WorkspaceConfig(**workspace_dict)

    def reload(self) -> None:
        """重新加载配置"""
        self._load_config()
        if self._initialized:
            self._initialize_logging()
            self._notify_change()
    
    def save_to_project(self) -> bool:
        """
        将当前运行时配置保存到项目配置文件
        
        Returns:
            保存是否成功
        """
        if not self._runtime_config:
            return True
        
        return self._config_loader.save_project_config(self._runtime_config)
    
    def reset_runtime_config(self) -> None:
        """重置运行时配置"""
        self._runtime_config.clear()
        self._notify_change()
    
    def on_config_change(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        注册配置变化回调
        
        Args:
            callback: 回调函数，接收完整配置作为参数
        """
        self._change_callbacks.append(callback)
    
    def get_full_config(self) -> Dict[str, Any]:
        """
        获取完整配置（合并运行时配置）
        
        Returns:
            完整配置字典
        """
        full_config = deepcopy(self._config)
        
        # 合并运行时配置
        for key, value in self._runtime_config.items():
            self._set_nested_value(full_config, key, value)
        
        return full_config
    
    def _get_nested_value(self, config: Dict[str, Any], key: str) -> Any:
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
    
    def _set_nested_value(self, config: Dict[str, Any], key: str, value: Any) -> None:
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
            if k not in current:
                current[k] = {}
            current = current[k]
        
        current[keys[-1]] = value
    
    def _notify_change(self) -> None:
        """通知配置变化"""
        full_config = self.get_full_config()
        for callback in self._change_callbacks:
            try:
                callback(full_config)
            except Exception as e:
                print(f"配置变化回调执行失败: {e}")
    
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