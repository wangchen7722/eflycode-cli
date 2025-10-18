"""
配置加载器

负责加载、合并和管理配置文件
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from copy import deepcopy
import tomllib

from eflycode.schema.config import LoggingConfig, ModelConfig

# 默认配置
DEFAULT_GLOBAL_CONFIG = {
    "logging": {
        "dirpath": str(Path.home() / ".eflycode" / "logs"),
        "filename": "echoai.log",
        "level": "INFO",
        "format": "{time:YYYY-MM-DD HH:mm:ss} | {level} | {file}:{function}:{line} | {message}",
        "rotation": "10 MB",
        "retention": "10 days",
        "encoding": "utf-8"
    }
}


def get_global_config_path():
    """获取全局配置文件路径"""
    config_dir = os.environ.get("EFLYCODE_USER_CONFIG_DIR")
    if not config_dir:
        config_dir = os.path.expanduser("~/.eflycode")

    return os.path.join(config_dir, "config.toml")


def get_workspace_dir():
    """获取工作空间目录"""
    workspace_dir = Path(os.getcwd())
    # 先检查当前运行路径下是否有 .eflycode 目录，如果没有，则尝试在上级目录查找，最多找 3 级目录
    for _ in range(4):
        eflycode_dir = workspace_dir / ".eflycode"
        if eflycode_dir.exists() and eflycode_dir.is_dir():
            return eflycode_dir
        # 向上一级目录
        workspace_dir = workspace_dir.parent

    # 如果都没找到，则返回当前工作目录下的默认路径
    eflycode_dir = Path(os.getcwd()) / ".eflycode"
    eflycode_dir.mkdir(parents=True, exist_ok=True)
    return eflycode_dir


def get_project_config_path():
    """获取项目配置文件路径"""
    return get_workspace_dir() / "config.toml"


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
        with open(file_path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        print(f"加载配置文件失败 {file_path}: {e}")
        return None


def deep_merge_config(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    深度合并两个配置字典
    
    Args:
        base: 基础配置
        override: 覆盖配置
        
    Returns:
        合并后的配置
    """
    result = deepcopy(base)

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # 递归合并字典
            result[key] = deep_merge_config(result[key], value)
        elif key == "entries" and isinstance(value, list) and isinstance(result.get(key), list):
            # 特殊处理model.entries列表：按model字段合并
            result[key] = merge_model_entries(result[key], value)
        else:
            # 直接覆盖
            result[key] = deepcopy(value)

    return result


def merge_model_entries(base_models: List[Dict], override_models: List[Dict]) -> List[Dict]:
    """
    合并模型配置列表
    
    Args:
        base_models: 基础模型列表
        override_models: 覆盖模型列表
        
    Returns:
        合并后的模型列表
    """
    result = deepcopy(base_models)
    base_model_map = {model.get("model"): i for i, model in enumerate(result)}

    for override_model in override_models:
        model_name = override_model.get("model")
        if model_name and model_name in base_model_map:
            # 更新现有模型
            idx = base_model_map[model_name]
            result[idx] = deep_merge_config(result[idx], override_model)
        else:
            # 添加新模型
            result.append(deepcopy(override_model))

    return result


def create_default_global_config(config_path: str) -> None:
    """
    创建默认全局配置文件
    
    Args:
        config_path: 配置文件路径
    """
    config_dir = os.path.dirname(config_path)
    os.makedirs(config_dir, exist_ok=True)

    with open(config_path, "w", encoding="utf-8") as f:
        # 写入TOML格式的默认配置
        f.write("""# EflyCode 全局配置文件

[logging]
dirpath = "logs"
filename = "eflycode.log"
level = "DEBUG"
format = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {file}:{function}:{line} | {message}"
rotation = "10 MB"
retention = "14 days"
encoding = "utf-8"
""")


class ConfigLoader:
    """配置加载器"""

    def __init__(self):
        self._global_config_path = get_global_config_path()
        self._project_config_path = get_project_config_path()

    def load_config(self) -> Dict[str, Any]:
        """
        加载完整配置
        
        Returns:
            合并后的配置字典
        """
        # 从默认配置开始
        config = deepcopy(DEFAULT_GLOBAL_CONFIG)

        # 加载全局配置
        global_config = self._load_global_config()
        if global_config:
            config = deep_merge_config(config, global_config)

        # 加载项目配置
        project_config = self._load_project_config()
        if project_config:
            config = deep_merge_config(config, project_config)

        return config

    def _load_global_config(self) -> Optional[Dict[str, Any]]:
        """加载全局配置"""
        config = load_config_file(self._global_config_path)
        if config is None and not os.path.exists(self._global_config_path):
            # 创建默认全局配置
            create_default_global_config(self._global_config_path)
            config = load_config_file(self._global_config_path)
        return config

    def _load_project_config(self) -> Optional[Dict[str, Any]]:
        """加载项目配置"""
        return load_config_file(self._project_config_path)

    def save_project_config(self, config: Dict[str, Any]) -> bool:
        """
        保存项目配置
        
        Args:
            config: 配置字典
            
        Returns:
            是否保存成功
        """
        try:
            config_dir = os.path.dirname(self._project_config_path)
            os.makedirs(config_dir, exist_ok=True)

            # 手动写入TOML格式
            with open(self._project_config_path, "w", encoding="utf-8") as f:
                self._write_toml_config(config, f)

            return True
        except Exception as e:
            print(f"保存项目配置失败: {e}")
            return False

    def _write_toml_config(self, config: Dict[str, Any], file) -> None:
        """
        手动写入TOML格式配置
        
        Args:
            config: 配置字典
            file: 文件对象
        """
        # 简单的TOML写入实现
        for section, values in config.items():
            if isinstance(values, dict):
                file.write(f"[{section}]\n")
                for key, value in values.items():
                    if isinstance(value, str):
                        file.write(f'{key} = "{value}"\n')
                    elif isinstance(value, bool):
                        file.write(f'{key} = {str(value).lower()}\n')
                    elif isinstance(value, (int, float)):
                        file.write(f'{key} = {value}\n')
                    elif isinstance(value, list):
                        # 处理数组表格
                        for item in value:
                            if isinstance(item, dict):
                                file.write(f"\n[[{section}.{key}]]\n")
                                for k, v in item.items():
                                    if isinstance(v, str):
                                        file.write(f'{k} = "{v}"\n')
                                    elif isinstance(v, bool):
                                        file.write(f'{k} = {str(v).lower()}\n')
                                    elif isinstance(v, (int, float)):
                                        file.write(f'{k} = {v}\n')
                file.write("\n")

    def get_config_paths(self) -> Dict[str, str]:
        """
        获取配置文件路径
        
        Returns:
            包含全局和项目配置路径的字典
        """
        return {
            "global": self._global_config_path,
            "project": self._project_config_path
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

    def get_model_config(self, config: Dict[str, Any]) -> ModelConfig:
        """
        获取模型配置
        
        Args:
            config: 完整配置字典
            
        Returns:
            模型配置对象
        """
        model_dict = config.get("model", {})
        return ModelConfig(**model_dict)

    def get_workspace_dir(self) -> str:
        """
        获取工作空间目录路径

        Returns:
            工作空间目录路径
        """
        return get_workspace_dir().as_posix()