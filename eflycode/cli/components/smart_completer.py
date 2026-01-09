"""智能命令补全器

统一处理所有命令的补全和执行
"""

import os
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document

from eflycode.core.config import resolve_workspace_dir
from eflycode.core.config.ignore import load_all_ignore_patterns, should_ignore_path


class SmartCompleter(Completer):
    """智能命令补全器，统一处理所有命令"""

    def __init__(self):
        """初始化 SmartCompleter"""
        self._commands: Dict[str, Dict[str, any]] = {}
        self._file_cache: list[str] = []
        self._file_cache_root: Optional[Path] = None
        self._file_cache_time: float = 0.0
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
        text = document.text_before_cursor
        token = self._get_current_token(text)

        # TODO: 扩展为支持 @ 的补全匹配逻辑
        if token.startswith("/"):
            # 如果已经输入了完整命令，不提供补全
            if token in self._commands:
                return
            
            # 查找匹配的命令
            for command, info in self._commands.items():
                if command.startswith(token):
                    # 使用完整命令替换当前输入片段
                    start_pos = -len(token)

                    yield Completion(
                        text=command,
                        start_position=start_pos,
                        display=command,
                        display_meta=info["description"],
                    )
        elif token.startswith("#"):
            query = token[1:]
            start_pos = -len(token)
            for path in self._iter_project_files(prefix=query):
                yield Completion(
                    text=f"#{path}",
                    start_position=start_pos,
                    display=f"#{path}",
                    display_meta="file",
                )
        # 如果输入为空，不提供补全，让用户自己输入 /
        elif text.strip() == "":
            return

    @staticmethod
    def _get_current_token(text: str) -> str:
        if not text:
            return ""
        stripped = text.rstrip()
        if not stripped:
            return ""
        idx = stripped.rfind(" ")
        return stripped[idx + 1 :]

    def _iter_project_files(self, prefix: str) -> Iterable[str]:
        files = self._get_project_files()
        count = 0
        for path in files:
            if not prefix or path.startswith(prefix):
                yield path
                count += 1
                if count >= 200:
                    break

    def _get_project_files(self) -> list[str]:
        workspace_dir = resolve_workspace_dir()
        now = time.monotonic()
        if (
            self._file_cache_root == workspace_dir
            and self._file_cache
            and (now - self._file_cache_time) < 2.0
        ):
            return self._file_cache

        ignore_patterns = load_all_ignore_patterns(workspace_dir=workspace_dir)
        default_excludes = {".git", "__pycache__", "node_modules", ".venv"}
        files: list[str] = []

        for root, dirs, filenames in os.walk(workspace_dir):
            root_path = Path(root)
            dirs[:] = [d for d in dirs if d not in default_excludes]
            if ignore_patterns:
                dirs[:] = [
                    d
                    for d in dirs
                    if not should_ignore_path(root_path / d, ignore_patterns, workspace_dir)
                ]
            for filename in filenames:
                path = root_path / filename
                if ignore_patterns and should_ignore_path(path, ignore_patterns, workspace_dir):
                    continue
                rel_path = path.relative_to(workspace_dir).as_posix()
                files.append(rel_path)

        self._file_cache = files
        self._file_cache_root = workspace_dir
        self._file_cache_time = now
        return files

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

