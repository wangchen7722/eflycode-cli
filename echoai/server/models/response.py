from functools import wraps
from typing import Any, Dict, Optional, Sequence
from pydantic import BaseModel

class ServerSentEvent:
    """
    服务器发送事件模型。
    """
    def __init__(self, data: Any, event: Optional[str] = None):
        """
        初始化服务器发送事件。
        """
        self.event = event
        self.data = data

    def encode(self, *args):
        """
        编码服务器发送事件。
        """
        if self.event is None:
            return f"data: {self.data}\n\n".encode(*args)
        return f"event: {self.event}\ndata: {self.data}\n\n".encode(*args)

    def __iter__(self):
        """
        迭代服务器发送事件。
        """
        if self.event is None:
            yield f"data: {self.data}\n\n"
        yield f"event: {self.event}\ndata: {self.data}\n\n"

    def __str__(self):
        """
        字符串化服务器发送事件。
        """
        if self.event is None:
            yield f"data: {self.data}\n\n"
        yield f"event: {self.event}\ndata: {self.data}\n\n"

class ResultResponse(BaseModel):
    """
    结果响应模型。
    """
    code: int = 20000
    """响应代码"""
    data: Any = None
    """响应数据"""
    message: Optional[str] = None
    """消息"""

    @classmethod
    def success(cls, data: Any = None):
        """
        创建一个成功的响应。
        """
        return cls(data=data)

    @classmethod
    def error(cls, code: int = 50000, message: Optional[str] = None, data: Any = None):
        """
        创建一个错误的响应。
        """
        return cls(code=code, message=message, data=data)

    model_config = {
        "exclude_none": True
    }

def result_response(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            data = await func(*args, **kwargs)
            return ResultResponse.success(data=data).model_dump(exclude_none=True)
        except Exception as e:
            raise e
    return wrapper