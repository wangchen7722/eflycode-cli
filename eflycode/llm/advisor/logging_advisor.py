from pathlib import Path

from eflycode.llm.advisor import Advisor, register_advisor
from eflycode.schema.llm import LLMRequest, Message
from eflycode.util.system import get_system_environment
from eflycode.prompt.prompt_loader import PromptLoader

class LoggingAdvisor(Advisor):
    """日志记录 Advisor
    
    将输入和输出打印到特定的文件中
    """
    
    def __init__(self) -> None:
        if not Path("logging.txt").exists():
            Path("logging.txt").touch()
        else:
            # 清空内容
            with open("logging.txt", "w", encoding="utf-8") as f:
                f.write("")
    
    def get_priority(self) -> int:
        return -101
    
    def is_builtin_advisor(self) -> bool:
        return True
    
    def before_call(self, request: LLMRequest) -> LLMRequest:
        with open("logging.txt", "a", encoding="utf-8") as f:
            for message in request.messages:
                f.write(f"## {message.role}\n{message.content}\n\n\n")
        return request
    
    def before_stream(self, request: LLMRequest) -> LLMRequest:
        with open("logging.txt", "a", encoding="utf-8") as f:
            for message in request.messages:
                f.write(f"## {message.role}\n{message.content}\n\n\n")
        return request