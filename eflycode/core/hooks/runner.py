"""Hook 执行器

负责执行 hook 命令并处理输入输出
"""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from eflycode.core.hooks.types import (
    CommandHook,
    HookEventName,
    HookExecutionResult,
    HookOutput,
)


class HookRunner:
    """Hook 执行器

    负责执行单个或多个 hooks
    """

    def __init__(self, workspace_dir: Optional[Path] = None):
        """初始化执行器

        Args:
            workspace_dir: 工作区目录
        """
        self.workspace_dir = workspace_dir or Path.cwd()

    def execute_hook(
        self,
        hook: CommandHook,
        event_name: HookEventName,
        input_data: Dict[str, Any],
        session_id: Optional[str] = None,
        workspace_dir: Optional[Path] = None,
    ) -> HookExecutionResult:
        """执行单个 hook

        Args:
            hook: Hook 定义
            event_name: 事件名称
            input_data: 输入数据（事件特定的字段）
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            HookExecutionResult: 执行结果
        """
        start_time = time.time()

        # 构造完整的输入数据
        full_input = self._build_input_data(
            event_name, input_data, session_id, workspace_dir or self.workspace_dir
        )

        # 展开环境变量
        command = self._expand_env_vars(
            hook.command, workspace_dir or self.workspace_dir, session_id
        )

        # 准备环境变量
        env = self._prepare_environment(
            workspace_dir or self.workspace_dir, session_id
        )

        try:
            # 执行命令
            process = subprocess.run(
                command,
                input=json.dumps(full_input, ensure_ascii=False),
                shell=True,
                capture_output=True,
                text=True,
                timeout=hook.timeout / 1000.0,  # 转换为秒
                cwd=str(workspace_dir or self.workspace_dir),
                env=env,
                encoding="utf-8",
                errors="replace",
            )

            duration_ms = int((time.time() - start_time) * 1000)

            return HookExecutionResult(
                hook_name=hook.name,
                stdout=process.stdout,
                stderr=process.stderr,
                exit_code=process.returncode,
                duration_ms=duration_ms,
                success=process.returncode == 0,
            )
        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            return HookExecutionResult(
                hook_name=hook.name,
                stdout="",
                stderr=f"Hook execution timeout after {hook.timeout}ms",
                exit_code=124,  # 超时退出码
                duration_ms=duration_ms,
                success=False,
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return HookExecutionResult(
                hook_name=hook.name,
                stdout="",
                stderr=f"Hook execution error: {str(e)}",
                exit_code=1,
                duration_ms=duration_ms,
                success=False,
            )

    def execute_hooks_parallel(
        self,
        hooks: List[CommandHook],
        event_name: HookEventName,
        input_data: Dict[str, Any],
        session_id: Optional[str] = None,
        workspace_dir: Optional[Path] = None,
    ) -> List[HookExecutionResult]:
        """并行执行多个 hooks

        Args:
            hooks: Hook 列表
            event_name: 事件名称
            input_data: 输入数据
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            List[HookExecutionResult]: 执行结果列表
        """
        import concurrent.futures

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(hooks)) as executor:
            futures = {
                executor.submit(
                    self.execute_hook,
                    hook,
                    event_name,
                    input_data,
                    session_id,
                    workspace_dir,
                ): hook
                for hook in hooks
            }

            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        return results

    def execute_hooks_sequential(
        self,
        hooks: List[CommandHook],
        event_name: HookEventName,
        initial_input_data: Dict[str, Any],
        session_id: Optional[str] = None,
        workspace_dir: Optional[Path] = None,
    ) -> List[HookExecutionResult]:
        """串行执行多个 hooks，将上一个的输出作为下一个的输入

        Args:
            hooks: Hook 列表
            event_name: 事件名称
            initial_input_data: 初始输入数据
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            List[HookExecutionResult]: 执行结果列表
        """
        results = []
        current_input = initial_input_data.copy()

        for hook in hooks:
            result = self.execute_hook(
                hook, event_name, current_input, session_id, workspace_dir
            )

            # 如果 hook 输出是 JSON，尝试解析并合并到输入中
            if result.success and result.stdout:
                try:
                    hook_output = HookOutput.from_json(result.stdout)
                    if hook_output.hook_specific_output:
                        # 将 hook_specific_output 合并到输入中
                        current_input.update(hook_output.hook_specific_output)
                except Exception:
                    # 解析失败，忽略
                    pass

            results.append(result)

            # 如果遇到阻断错误，停止执行
            if result.is_blocking:
                break

        return results

    def _build_input_data(
        self,
        event_name: HookEventName,
        event_data: Dict[str, Any],
        session_id: Optional[str],
        workspace_dir: Path,
    ) -> Dict[str, Any]:
        """构造完整的输入数据

        Args:
            event_name: 事件名称
            event_data: 事件特定的数据
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            Dict[str, Any]: 完整的输入数据
        """
        import datetime

        input_data = {
            "session_id": session_id or "",
            "hook_event_name": event_name.value,
            "cwd": str(Path.cwd()),
            "workspace_dir": str(workspace_dir),
            "timestamp": datetime.datetime.now().isoformat(),
        }

        # 合并事件特定的数据
        input_data.update(event_data)

        return input_data

    def _expand_env_vars(
        self, command: str, workspace_dir: Path, session_id: Optional[str]
    ) -> str:
        """展开命令中的环境变量

        Args:
            command: 命令字符串
            workspace_dir: 工作区目录
            session_id: 会话 ID

        Returns:
            str: 展开后的命令
        """
        # 获取系统版本
        from eflycode.core.config.config_manager import ConfigManager

        config_manager = ConfigManager.get_instance()
        version = config_manager._load_version()

        env_vars = {
            "EFLYCODE_PROJECT_DIR": str(workspace_dir),
            "EFLYCODE_WORKSPACE_DIR": str(workspace_dir),
            "EFLYCODE_CLI_VERSION": version,
            "EFLYCODE_SESSION_ID": session_id or "",
        }

        # 展开环境变量
        expanded = command
        for key, value in env_vars.items():
            expanded = expanded.replace(f"${key}", value)

        return expanded

    def _prepare_environment(
        self, workspace_dir: Path, session_id: Optional[str]
    ) -> Dict[str, str]:
        """准备环境变量

        Args:
            workspace_dir: 工作区目录
            session_id: 会话 ID

        Returns:
            Dict[str, str]: 环境变量字典
        """
        from eflycode.core.config.config_manager import ConfigManager

        config_manager = ConfigManager.get_instance()
        version = config_manager._load_version()

        env = os.environ.copy()
        env.update(
            {
                "EFLYCODE_PROJECT_DIR": str(workspace_dir),
                "EFLYCODE_WORKSPACE_DIR": str(workspace_dir),
                "EFLYCODE_CLI_VERSION": version,
                "EFLYCODE_SESSION_ID": session_id or "",
            }
        )

        return env

