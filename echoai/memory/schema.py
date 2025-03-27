from typing import Dict, List, Optional, Any, Sequence, Union
from enum import Enum
import time
from pydantic import BaseModel, Field

class MemoryItemType(Enum):

    CONTEXT = "context"
    MESSAGES = "messages"
    
    def __repr__(self):
        return self.value
    
    def __str__(self):
        return self.value

class MemoryItem(BaseModel):
    """记忆项模型"""

    id: str = Field(..., description="唯一标识符")
    type: MemoryItemType = Field(..., description="记忆类型")
    content: Union[str, List[Dict[str, Any]]] = Field(..., description="记忆内容")
    score: Optional[float] = Field(None, description="查询相似度得分")
    timestamp: float = Field(default_factory=time.time, description="创建时间戳")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "score": self.score,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        """从字典创建记忆项"""
        if "type" in data:
            data["type"] = MemoryItemType(data["type"])
        return cls(**data)