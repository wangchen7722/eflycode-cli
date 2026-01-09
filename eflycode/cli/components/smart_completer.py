"""智能命令补全器

统一处理所有命令的补全和执行
"""

from typing import Callable, Dict, Iterable, Optional

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document


class SmartCompleter(Completer):
    """智能命令补全器，统一处理所有命令"""

    def __init__(self):
        """初始化 SmartCompleter"""
        self._commands: Dict[str, Dict[str, any]] = {}
        self._register_default_commands()

    def _register_default_commands(self) -> None:
        """注册默认命令"""
        self.register_command(
            command="/model",
            description="选择模型配置",
            handler=None,  # handler 在外部设置
        )

    def register_command(
        self,
        command: str,
        description: str,
        handler: Optional[Callable[[str], bool]] = None,
    ) -> None:
        """注册新命令

        Args:
            command: 命令字符串，如 "/model"
            description: 命令描述
            handler: 命令处理函数，接收命令字符串，返回是否已处理
        """
        if not command.startswith("/"):
            raise ValueError(f"命令必须以 '/' 开头: {command}")

        self._commands[command] = {
            "description": description,
            "handler": handler,
        }

    def get_completions(
        self, document: Document, complete_event
    ) -> Iterable[Completion]:
        """获取补全建议

        Args:
            document: 当前文档
            complete_event: 补全事件

        Yields:
            Completion: 补全建议
        """
        text = document.text_before_cursor.strip()

        # 如果输入以 / 开头，提供命令补全
        if text.startswith("/"):
            # 如果已经输入了完整命令，不提供补全
            if text in self._commands:
                return
            
            # 查找匹配的命令
            for command, info in self._commands.items():
                if command.startswith(text):
                    # 补全部分命令
                    remaining = command[len(text) :]
                    start_pos = -len(text)

                    yield Completion(
                        text=remaining,
                        start_position=start_pos,
                        display=command,
                        display_meta=info["description"],
                    )
        # 如果输入为空，不提供补全，让用户自己输入 /
        elif text == "":
            return

    def handle_command(self, command: str) -> bool:
        """处理命令

        Args:
            command: 命令字符串

        Returns:
            bool: 如果命令已处理返回 True，否则返回 False
        """
        command = command.strip()
        if command in self._commands:
            handler = self._commands[command].get("handler")
            if handler:
                return handler(command)
        return False

    def get_command_handler(self, command: str) -> Optional[Callable[[str], bool]]:
        """获取命令处理函数

        Args:
            command: 命令字符串

        Returns:
            Optional[Callable]: 命令处理函数，如果不存在返回 None
        """
        if command in self._commands:
            return self._commands[command].get("handler")
        return None

    def set_command_handler(self, command: str, handler: Callable[[str], bool]) -> None:
        """设置命令处理函数

        Args:
            command: 命令字符串
            handler: 命令处理函数
        """
        if command not in self._commands:
            raise ValueError(f"命令未注册: {command}")
        self._commands[command]["handler"] = handler

