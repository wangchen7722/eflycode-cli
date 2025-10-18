from typing import Any, List, Optional
from pathlib import Path
from pydantic import BaseModel, Field

from eflycode.constant import EFLYCODE_PROJECT_HOME_DIR


class DictBaseModel(BaseModel):
    """字典基础模型"""

    def __getitem__(self, key: str) -> Any:
        """获取字典项"""
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(f"字典模型 {self.__class__.__name__} 中不存在键 {key}")

    def __setitem__(self, key: str, value: Any) -> None:
        """设置字典项"""
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            raise KeyError(f"字典模型 {self.__class__.__name__} 中不存在键 {key}")

    def __contains__(self, key: str) -> bool:
        """检查字典项是否存在"""
        return hasattr(self, key)

    def keys(self):
        return type(self).model_fields.keys()

    def values(self):
        return [getattr(self, k) for k in type(self).model_fields.keys()]

    def items(self):
        return [(k, getattr(self, k)) for k in type(self).model_fields.keys()]


class LoggingConfig(DictBaseModel):
    """日志配置"""
    dirpath: Path = Field(default=EFLYCODE_PROJECT_HOME_DIR / "logs", description="日志目录")
    filename: str = Field(default="echoai.log", description="日志文件名")
    level: str = Field(default="INFO", description="日志级别")
    format: str = Field(default="{time:YYYY-MM-DD HH:mm:ss} | {level} | {file}:{function}:{line} | {message}",
                        description="日志格式")
    rotation: str = Field(default="10 MB", description="日志旋转")
    retention: str = Field(default="10 days", description="日志保留")
    encoding: str = Field(default="utf-8", description="日志编码")


class ModelEntry(DictBaseModel):
    """模型配置项"""

    model: str = Field(description="模型ID")
    name: str = Field(description="模型名称")
    provider: str = Field(description="模型提供方")
    api_key: str = Field(description="API密钥")
    base_url: str = Field(description="基础URL")
    max_context_length: int = Field(description="最大上下文长度")
    temperature: float = Field(description="温度")
    supports_native_tool_call: bool = Field(default=False, description="是否支持原生函数调用")


class ModelConfig(DictBaseModel):
    """模型配置"""

    default: str = Field(description="默认模型")
    entries: List[ModelEntry] = Field(description="模型列表")

    def get_default_entry(self) -> ModelEntry:
        """获取默认模型配置项"""
        for entry in self.entries:
            if entry.model == self.default:
                return entry
        raise ValueError(f"默认模型 {self.default} 不在模型列表中")


class LLMConfig(DictBaseModel):
    """模型配置项"""

    model: str = Field(description="模型ID")
    name: str = Field(description="模型名称")
    provider: str = Field(description="模型提供方")
    api_key: str = Field(description="API密钥")
    base_url: str = Field(description="基础URL")
    max_context_length: int = Field(description="最大上下文长度")
    supports_native_tool_call: bool = Field(
        default=False, description="是否支持原生函数调用"
    )
    temperature: float = Field(default=0.2, description="温度")


class RuntimeConfig(DictBaseModel):
    """运行时配置"""

    workspace_dir: Optional[Path] = Field(default=None, description="当前工作目录")
    settings_dir: Optional[Path] = Field(default=None, description="设置目录")
    settings_file: Optional[Path] = Field(default=None, description="设置文件")


class AppConfig(DictBaseModel):
    """应用配置"""

    logging: LoggingConfig = Field(default_factory=LoggingConfig, description="日志配置")
    model: Optional[ModelConfig] = Field(default_factory=ModelConfig, description="模型配置")
