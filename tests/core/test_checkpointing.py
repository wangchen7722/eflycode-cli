import hashlib
import unittest
from pathlib import Path

from eflycode.core.config.config_manager import get_checkpointing_enabled
from eflycode.core.utils.checkpoint import (
    ensure_checkpoint_dirs,
    get_checkpoints_dir,
    get_history_dir,
)


class TestCheckpointing(unittest.TestCase):
    """Checkpointing 功能测试类"""

    def test_checkpoint_dirs_creation(self):
        """测试 checkpoint 目录创建"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_dir = Path(tmp_dir) / "workspace"
            workspace_dir.mkdir()

            history_dir = get_history_dir(workspace_dir)
            checkpoints_dir = get_checkpoints_dir(workspace_dir)

            # 目录名包含 workspace 哈希
            workspace_hash = hashlib.sha256(str(workspace_dir.resolve()).encode("utf-8")).hexdigest()
            self.assertIn(workspace_hash, str(history_dir))
            self.assertIn(workspace_hash, str(checkpoints_dir))

            h_dir, c_dir = ensure_checkpoint_dirs(workspace_dir)
            self.assertTrue(h_dir.exists())
            self.assertTrue(c_dir.exists())

    def test_get_checkpointing_enabled(self):
        """测试获取 checkpointing 开关状态"""
        self.assertFalse(get_checkpointing_enabled({}))
        self.assertTrue(get_checkpointing_enabled({"checkpointing": {"enabled": True}}))
        self.assertFalse(get_checkpointing_enabled({"checkpointing": {"enabled": False}}))


if __name__ == "__main__":
    unittest.main()
