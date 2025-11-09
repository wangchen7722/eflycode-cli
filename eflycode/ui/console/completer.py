from typing import Iterable, List
from prompt_toolkit.completion import Completer, Completion, CompleteEvent
from prompt_toolkit.document import Document

from eflycode.ui.command import BaseCommand, get_builtin_commands


class SmartCompleter(Completer):
    """命令、技能、文件路径的智能补全器"""

    def __init__(self):
        self.commands: List[BaseCommand] = get_builtin_commands()
        self.skills: List[str] = []
        self.files: List[str] = []
        self.max_command_length = max((len(cmd.name) for cmd in self.commands), default=0)

    def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        """根据当前输入返回命令补全建议"""
        text = document.text_before_cursor.strip()
        if not text:
            return

        # 限制匹配范围：只保留末尾可能的命令部分
        text = text[-self.max_command_length:]
        slash_index = text.rfind("/")
        if slash_index != -1:
            prefix = text[slash_index + 1:]
            for cmd in self.commands:
                if cmd.name.startswith(prefix):
                    yield Completion(
                        cmd.name,
                        display=cmd.description,
                        start_position=-len(prefix)
                    )
