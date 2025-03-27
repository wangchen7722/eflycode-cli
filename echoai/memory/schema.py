from typing import Dict, Optional, Any, Sequence, Union
from enum import Enum
import time
from pydantic import BaseModel, Field


class MemoryType(Enum):
    """记忆类型枚举"""
    SHORT_TERM = "short_term"  # 短期记忆
    LONG_TERM = "long_term"  # 长期记忆


class MemoryItem(BaseModel):
    """记忆项模型"""
    id: str = Field(..., description="唯一标识符")
    content: str = Field(..., description="记忆内容")
    type: MemoryType = Field(..., description="记忆类型")
    timestamp: float = Field(default_factory=time.time, description="创建时间戳")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    embedding: Optional[Union[Sequence[float], Sequence[int]]] = Field(None, description="向量嵌入")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "content": self.content,
            "type": self.type.value,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        """从字典创建记忆项"""
        if "type" in data and isinstance(data["type"], str):
            data["type"] = MemoryType(data["type"])
        return cls(**data)

    def to_message(self) -> Dict[str, Any]:
        """转换为大模型消息格式
        
        Returns:
            Dict[str, Any]: 消息字典，包含role和content字段
        """
        # 根据记忆类型设置角色
        role = self.metadata.get("role", "assistant")

        # 构建消息内容
        message = {
            "role": role,
            "content": self.content
        }

        # 如果有工具调用相关的元数据，添加到消息中
        if "tool_call_id" in self.metadata:
            message["tool_call_id"] = self.metadata["tool_call_id"]
        if "name" in self.metadata:
            message["name"] = self.metadata["name"]
        if "tool_calls" in self.metadata:
            message["tool_calls"] = self.metadata["tool_calls"]

        return message
