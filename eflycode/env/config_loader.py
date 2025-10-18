"""
配置加载器

负责加载、合并和管理配置文件
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from copy import deepcopy
import toml

from eflycode.util.logger import logger
from eflycode.schema.config import AppConfig, LoggingConfig, RuntimeConfig

# 默认配置
DEFAULT_CONFIG = {
    "logging": {
        "dirpath": (Path.home() / ".eflycode" / "logs").as_posix(),
        "filename": "eflycode.log",
        "level": "WARNING",
        "format": "{time:YYYY-MM-DD HH:mm:ss} | {level} | {file}:{function}:{line} | {message}",
        "rotation": "10 MB",
        "retention": "14 days",
        "encoding": "utf-8"
    }
}


def to_posix(path: Path | str) -> str:
    """将路径转换为 POSIX 格式"""
    if isinstance(path, str):
        path = Path(path)
    return path.as_posix()


def get_global_settings_dir() -> Path:
    """获取全局配置文件路径"""
    global_settings_dir = Path.home() / ".eflycode"
    global_settings_dir.mkdir(parents=True, exist_ok=True)
    return global_settings_dir


def get_workspace_dir() -> Path:
    """获取工作空间目录"""
    workspace_dir = Path(os.getcwd())
    # 先检查当前运行路径下是否有 .eflycode 目录，如果没有，则尝试在上级目录查找，最多找 3 级目录
    # 如果有 .eflycode 目录，则返回当前运行路径
    for _ in range(4):
        eflycode_dir = workspace_dir / ".eflycode"
        if eflycode_dir.exists() and eflycode_dir.is_dir():
            return workspace_dir
        # 向上一级目录
        workspace_dir = workspace_dir.parent

    # 如果都没找到，则返回当前工作目录下的默认路径
    eflycode_dir = Path(os.getcwd()) / ".eflycode"
    eflycode_dir.mkdir(parents=True, exist_ok=True)
    return eflycode_dir.parent


def get_project_config_path() -> Path:
    """获取项目配置文件路径"""
    return get_workspace_dir() / ".eflycode" / "config.toml"


def load_config_file(file_path: str) -> Optional[Dict[str, Any]]:
    """
    加载TOML配置文件
    
    Args:
        file_path: 配置文件路径
        
    Returns:
        配置字典，如果文件不存在或加载失败则返回None
    """
    if not Path(file_path).exists():
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return toml.loads(f.read())
    except Exception as e:
        logger.exception(f"加载配置文件失败 {file_path}: {e}")
        return None


def dump_config_file(config: Dict[str, Any], file_path: str) -> None:
    """
    保存 TOML 配置文件
    
    Args:
        config: 配置字典
        file_path: 配置文件路径
    """
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(toml.dumps(config))
    except Exception as e:
        logger.exception(f"保存配置文件失败 {file_path}: {e}")
        return None


def deep_merge_config(base: Dict[str, Any], override: Dict[str, Any], is_overwrite: bool = False) -> Dict[str, Any]:
    """
    深度合并两个配置字典
    
    Args:
        base: 基础配置
        override: 覆盖配置
        is_overwrite: 是否覆盖存在的键值对，默认 False
        
    Returns:
        合并后的配置
    """
    # 深度合并字典
    merged = deepcopy(base)

    for key, value in override.items():
        base_value = merged.get(key)

        if base_value is None:
            # 直接添加新键值对
            merged[key] = deepcopy(value)
        elif isinstance(base_value, dict) and isinstance(value, dict):
            # 递归合并字典
            merged[key] = deep_merge_config(base_value, value, is_overwrite)
        elif isinstance(base_value, list) and isinstance(value, list):
            # 合并列表并去重
            merged[key] = [
                deepcopy(item) for item in set(base_value + value)
            ]
        else:
            # 直接覆盖
            if is_overwrite:
                merged[key] = deepcopy(value)

    return merged


def create_default_global_config(config_path: str) -> None:
    """
    创建默认全局配置文件
    
    Args:
        config_path: 配置文件路径
    """
    config_path = Path(config_path)
    config_dir = config_path.parent
    config_dir.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w", encoding="utf-8") as f:
        toml.dump(DEFAULT_CONFIG, f)


class ConfigLoader:
    """配置加载器"""

    SETTINGS_FOLDER = ".eflycode"
    CONFIG_FILENAME = "config.toml"

    def __init__(self):
        self._global_settings_dir = get_global_settings_dir()
        self._workspace_settings_dir = get_workspace_dir() / self.SETTINGS_FOLDER
        self._global_settings_file = self._global_settings_dir / self.CONFIG_FILENAME
        self._workspace_settings_file = self._workspace_settings_dir / self.CONFIG_FILENAME

    def load_config(self) -> AppConfig:
        """
        加载完整配置
        
        Returns:
            合并后的配置字典
        """
        # 从默认配置开始
        config = deepcopy(DEFAULT_CONFIG)

        # 加载全局配置
        global_config = self._load_global_config()
        if global_config:
            config = deep_merge_config(config, global_config, is_overwrite=True)

        # 加载工作空间配置
        workspace_config = self._load_workspace_config()
        if workspace_config:
            config = deep_merge_config(config, workspace_config, is_overwrite=True)

        return AppConfig(**config)

    def _load_global_config(self) -> Optional[Dict[str, Any]]:
        """加载全局配置"""
        config = load_config_file(to_posix(self._global_settings_file))
        if config is None and not self._global_settings_file.exists():
            # 创建默认全局配置
            create_default_global_config(to_posix(self._global_settings_file))
            config = load_config_file(to_posix(self._global_settings_file))
        return config

    def _load_workspace_config(self) -> Optional[Dict[str, Any]]:
        """加载工作空间配置"""
        return load_config_file(to_posix(self._workspace_settings_file))

    def save_workspace_settings(self, config: Dict[str, Any]) -> bool:
        """
        保存工作空间配置
        
        Args:
            config: 配置字典
            
        Returns:
            是否保存成功
        """
        try:
            self._workspace_settings_dir.mkdir(parents=True, exist_ok=True)
            dump_config_file(config, to_posix(self._workspace_settings_file))

            return True
        except Exception as e:
            logger.exception(f"保存工作空间配置失败: {e}")
            return False

    def get_config_paths(self) -> Dict[str, str]:
        """
        获取配置文件路径
        
        Returns:
            包含全局和项目配置路径的字典
        """
        return {
            "global": (self._global_settings_dir / self.CONFIG_FILENAME).as_posix(),
            "workspace": (self._workspace_settings_dir / self.CONFIG_FILENAME).as_posix()
        }

    def get_logging_config(self, config: Dict[str, Any]) -> LoggingConfig:
        """
        获取日志配置
        
        Args:
            config: 完整配置字典
            
        Returns:
            日志配置对象
        """
        logging_dict = config.get("logging", {})
        return LoggingConfig(**logging_dict)

    def get_runtime_config(self) -> RuntimeConfig:
        """
        获取运行时配置
        
        Returns:
            运行时配置对象
        """
        runtime_config = {
            "workspace_dir": self._workspace_settings_dir.parent.as_posix(),
            "settings_dir": self._workspace_settings_dir.as_posix(),
            "settings_file": self._workspace_settings_file.as_posix(),
        }
        return RuntimeConfig(**runtime_config)

    def get_workspace_dir(self) -> str:
        """
        获取工作空间目录路径

        Returns:
            工作空间目录路径
        """
        return get_workspace_dir().as_posix()
