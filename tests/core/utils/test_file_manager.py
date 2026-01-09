"""FileManager 测试"""

import tempfile
import time
import unittest
from pathlib import Path

from eflycode.core.utils.file_manager import FileManager


class TestFileManager(unittest.TestCase):
    """FileManager 测试类"""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        (self.temp_dir / ".eflycode").mkdir(parents=True, exist_ok=True)
        (self.temp_dir / "src" / "utils").mkdir(parents=True, exist_ok=True)
        (self.temp_dir / "ignored_dir").mkdir(parents=True, exist_ok=True)
        (self.temp_dir / "node_modules").mkdir(parents=True, exist_ok=True)

        (self.temp_dir / ".eflycode" / ".eflycodeignore").write_text(
            "secret.txt\n", encoding="utf-8"
        )
        (self.temp_dir / ".gitignore").write_text(
            "ignored.txt\nignored_dir/\n", encoding="utf-8"
        )

        (self.temp_dir / "src" / "main.py").write_text("", encoding="utf-8")
        (self.temp_dir / "src" / "utils" / "file_manager.py").write_text(
            "", encoding="utf-8"
        )
        (self.temp_dir / "README.md").write_text("", encoding="utf-8")
        (self.temp_dir / "ignored.txt").write_text("", encoding="utf-8")
        (self.temp_dir / "secret.txt").write_text("", encoding="utf-8")
        (self.temp_dir / "ignored_dir" / "skip.py").write_text(
            "", encoding="utf-8"
        )
        (self.temp_dir / "node_modules" / "skip.js").write_text(
            "", encoding="utf-8"
        )

    def test_get_files_respects_ignore(self) -> None:
        manager = FileManager(self.temp_dir, refresh_interval=0)
        files = manager.get_files()

        self.assertIn("src/main.py", files)
        self.assertIn("src/utils/file_manager.py", files)
        self.assertIn("README.md", files)
        self.assertNotIn("ignored.txt", files)
        self.assertNotIn("secret.txt", files)
        self.assertNotIn("ignored_dir/skip.py", files)
        self.assertNotIn("node_modules/skip.js", files)

    def test_fuzzy_find(self) -> None:
        manager = FileManager(self.temp_dir, refresh_interval=0)
        matches = manager.fuzzy_find("smpy")
        self.assertIn("src/main.py", matches)
        self.assertEqual(matches[0], "src/main.py")

        matches = manager.fuzzy_find("fm")
        self.assertIn("src/utils/file_manager.py", matches)

    def test_watcher_refreshes_cache(self) -> None:
        manager = FileManager(
            self.temp_dir, refresh_interval=0, watch_interval=0.05
        )
        manager.start_watching()
        try:
            new_file = self.temp_dir / "src" / "new_file.py"
            new_file.write_text("", encoding="utf-8")

            deadline = time.monotonic() + 1.0
            found = False
            while time.monotonic() < deadline:
                if "src/new_file.py" in manager.get_files():
                    found = True
                    break
                time.sleep(0.05)
            self.assertTrue(found)
        finally:
            manager.stop_watching()


if __name__ == "__main__":
    unittest.main()
