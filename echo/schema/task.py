from datetime import datetime
from typing import Optional, Dict, Any, Tuple, TypeVar, Generic, Literal, List, Union
from pydantic import BaseModel, FileUrl, HttpUrl, Field
from enum import Enum
import uuid

from echo.schema.agent import AgentResponse
from echo.schema.llm import Usage


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
        timestamp: 时间戳
        role: 角色类型
        content: 内容
        response: Agent响应，包含工具调用、检索文档等详细信息
        references: 引用
        metadata: 元数据
    """
    task_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: datetime = Field(default_factory=datetime.now)
    role: Literal["user", "assistant"]
    content: Optional[str] = None
    response: Optional[AgentResponse] = None
    references: Optional[List[BaseReference]] = None
    metadata: Optional[Dict[str, Any]] = None


class ConversationTask(BaseModel):
    """对话任务

    Attributes:
        task_id: 任务ID
        task_name: 任务名称
        start_time: 开始时间
        end_time: 结束时间
        total_usage: 总Token使用量
        records: 执行记录列表
        iterations: 迭代次数
        metadata: 元数据
    """
    task_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    task_name: str
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    total_usage: Usage = Field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    records: List[ConversationMessage] = Field(default_factory=list)
    iterations: int = 0
    metadata: Optional[Dict[str, Any]] = None
    
    def get_duration(self) -> Optional[float]:
        """获取任务持续时间（秒）"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    def finish(self) -> None:
        """结束任务会话"""
        self.end_time = datetime.now()
    
    def record(self, record: ConversationMessage) -> None:
        """添加执行记录"""
        self.records.append(record)
        # 更新Token使用统计
        if record.role == "assistant" and record.response and record.response.usage:
            usage = record.response.usage
            self.total_usage = {
                "prompt_tokens": self.total_usage.prompt_tokens + usage.prompt_tokens,
                "completion_tokens": self.total_usage.completion_tokens + usage.completion_tokens,
                "total_tokens": self.total_usage.total_tokens + usage.total_tokens
            }
    
    def iteration(self) -> None:
        """增加迭代次数"""
        self.iterations += 1
    
    def __enter__(self):
        """进入上下文管理器"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文管理器，自动结束任务"""
        self.finish()
        return False
