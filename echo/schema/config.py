from typing import List
from pathlib import Path
from pydantic import BaseModel, Field

from echo.constant import ECHO_PROJECT_HOME_DIR

class LoggingConfig(BaseModel):
    """日志配置"""
    dirpath: Path = Field(default=ECHO_PROJECT_HOME_DIR / "logs", description="日志目录")
    filename: str = Field(default="echoai.log", description="日志文件名")
    level: str = Field(default="INFO", description="日志级别")
    format: str = Field(default="{time:YYYY-MM-DD HH:mm:ss} | {level} | {file}:{function}:{line} | {message}", description="日志格式")
    rotation: str = Field(default="10 MB", description="日志旋转")
    retention: str = Field(default="10 days", description="日志保留")
    encoding: str = Field(default="utf-8", description="日志编码")

class ModelEntry(BaseModel):
    """模型配置项"""

    model: str = Field(description="模型ID")
    name: str = Field(description="模型名称")
    provider: str = Field(description="模型提供方")
    api_key: str = Field(description="API密钥")
    base_url: str = Field(description="基础URL")
    max_context_length: int = Field(description="最大上下文长度")
    temperature: float = Field(description="温度")
    support_native_tool_call: bool = Field(default=False, description="是否支持原生函数调用")


class ModelConfig(BaseModel):
    """模型配置"""

    default: str = Field(description="默认模型")
    entries: List[ModelEntry] = Field(description="模型列表")
