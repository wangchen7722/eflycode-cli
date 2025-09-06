from datetime import datetime
from typing import Optional, Dict, Any, Tuple, TypeVar, Generic, Literal, List
from pydantic import BaseModel, FileUrl, HttpUrl, Field
from enum import Enum
import uuid

from echo.schema.agent import AgentResponse


E = TypeVar("E", bound=Enum)

class ReferenceType(str, Enum):
    """引用类型

    Attributes:
        file: 文件引用
        text_snippet: 文本片段引用
        url: 网址引用
        terminal: 终端引用
    """
    file = "file"
    text_snippet = "text_snippet"
    url = "url"
    terminal = "terminal"


class BaseReference(BaseModel, Generic[E]):
    """引用基类

    Attributes:
        ref_id: 引用ID
        type: 引用类型
    """
    ref_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    type: E

class FileReference(BaseReference[Literal[ReferenceType.file]]):
    uri: FileUrl
    metadata: Optional[Dict[str, Any]] = None

class UrlReference(BaseReference[Literal[ReferenceType.url]]):
    """网址引用

    Attributes:
        url: 网址
    """
    url: HttpUrl

class TextSnippetReference(BaseReference[Literal[ReferenceType.text_snippet]]):
    """文本片段引用

    Attributes:
        text: 文本内容
        text_range: 文本范围，格式为 ((start_line, start_char), (end_line, end_char))
    """
    text: str
    text_range: Tuple[Tuple[int, int], Tuple[int, int]]

class TerminalReference(BaseReference[Literal[ReferenceType.terminal]]):
    """终端引用

    Attributes:
        command: 终端命令
        working_dir: 工作目录
        exit_code: 退出码
        stdout: 标准输出
        stderr: 标准错误输出
    """
    command: str
    working_dir: Optional[str] = None
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None

class ConversationMessage(BaseModel):
    """对话消息

    Attributes:
        task_id: 任务ID
        message_id: 消息ID
        start_time: 开始时间
        end_time: 结束时间
        role: 角色
        content: 内容
        references: 引用
        metadata: 元数据
    """
    task_id: str
    message_id: str
    start_time: datetime
    end_time: datetime
    role: Literal["user", "assistant"]
    content: str | AgentResponse
    references: Optional[List[BaseReference]] = None
    metadata: Optional[Dict[str, Any]] = None

class ConversationTask(BaseModel):
    """对话任务

    Attributes:
        task_id: 任务ID
        start_time: 开始时间
        end_time: 结束时间
        metadata: 元数据
    """
    task_id: str
    start_time: datetime
    end_time: datetime
    metadata: Optional[Dict[str, Any]] = None
