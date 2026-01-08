"""Shadow Git 仓库服务，用于 checkpointing 快照与恢复"""

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from eflycode.core.utils.checkpoint import ensure_checkpoint_dirs


class CheckpointError(Exception):
    """Checkpoint 相关操作失败"""


class GitService:
    """管理 shadow git 仓库"""

    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir.resolve()
        history_dir, _ = ensure_checkpoint_dirs(self.workspace_dir)
        self.history_dir = history_dir
        self.git_dir = self.history_dir / ".git"
        self.env = {
            "GIT_DIR": str(self.git_dir),
            "GIT_WORK_TREE": str(self.workspace_dir),
        }

    def _run_git(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """带环境变量运行 git 命令"""
        try:
            return subprocess.run(
                ["git", *args],
                cwd=self.workspace_dir,
                env={**self.env, **dict(GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=check,
            )
        except FileNotFoundError as e:
            raise CheckpointError("Git 未安装或不可用") from e
        except subprocess.CalledProcessError as e:
            raise CheckpointError(e.stderr.strip() or str(e)) from e

    def initialize(self) -> None:
        """初始化 shadow 仓库"""
        # 检查 git 是否可用
        self._run_git(["--version"], check=True)

        # 初始化仓库
        if not self.git_dir.exists():
            self.history_dir.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "init"],
                cwd=self.history_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
            )
            # 基本 config
            self._run_git(["config", "user.name", "eflycode-checkpoint"])
            self._run_git(["config", "user.email", "checkpoint@eflycode.local"])
            self._run_git(["config", "commit.gpgsign", "false"])

        # 同步 .gitignore（最佳努力）
        workspace_gitignore = self.workspace_dir / ".gitignore"
        if workspace_gitignore.exists():
            dest = self.history_dir / ".gitignore"
            try:
                shutil.copy(workspace_gitignore, dest)
            except Exception:
                # 忽略复制失败
                pass

    def get_current_hash(self) -> Optional[str]:
        """获取当前 HEAD 哈希（可能为空仓库）"""
        try:
            result = self._run_git(["rev-parse", "HEAD"])
            return result.stdout.strip()
        except CheckpointError:
            return None

    def create_snapshot(self, tool_name: str) -> Optional[str]:
        """创建快照，返回提交哈希；无变更时返回当前哈希"""
        self.initialize()

        # add 所有改动
        try:
            self._run_git(["add", "-A"])
        except CheckpointError:
            return self.get_current_hash()

        # 判断是否有 staged 变更
        status = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            env=self.env,
            cwd=self.workspace_dir,
        )
        has_changes = status.returncode == 1
        if not has_changes:
            return self.get_current_hash()

        # 提交
        message = f"Snapshot for {tool_name}"
        self._run_git(["commit", "-m", message])

        return self.get_current_hash()

    def restore(self, commit_hash: str) -> None:
        """恢复到指定哈希"""
        if not commit_hash:
            raise CheckpointError("无效的快照哈希")
        self.initialize()
        # restore 文件
        self._run_git(["restore", "--source", commit_hash, "."])
        # 清理新增文件
        self._run_git(["clean", "-fd"])

