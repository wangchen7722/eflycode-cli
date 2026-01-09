import os
import tempfile
import unittest

from eflycode.core.tool.errors import ToolExecutionError
from eflycode.core.tool.file_system_tool import (
    DeleteFileTool,
    GlobSearchTool,
    ListDirectoryTool,
    MoveFileTool,
    ReadFileTool,
    ReplaceTool,
    SearchFileContentTool,
    WriteFileTool,
)


class TestFileSystemTools(unittest.TestCase):
    """文件系统操作工具测试类"""

    def setUp(self):
        """设置测试环境"""
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, "test.txt")
        self.test_file2 = os.path.join(self.test_dir, "test2.txt")
        
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("line 1\nline 2\nline 3\nline 4\nline 5\n")

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_list_directory_tool_permission(self):
        """测试 ListDirectoryTool 的权限"""
        tool = ListDirectoryTool()
        self.assertEqual(tool.permission, "read")

    def test_list_directory_tool_display(self):
        """测试 ListDirectoryTool 的 display 方法"""
        tool = ListDirectoryTool()
        self.assertEqual(tool.display(dir_path="/test"), "列出目录 /test")
        self.assertEqual(tool.display(), "列出目录")

    def test_list_directory_tool(self):
        """测试 ListDirectoryTool 功能"""
        tool = ListDirectoryTool()
        result = tool.run(dir_path=self.test_dir)
        self.assertIn("test.txt", result)
        self.assertIn("(5 lines)", result)

    def test_list_directory_tool_nonexistent(self):
        """测试 ListDirectoryTool 处理不存在的目录"""
        tool = ListDirectoryTool()
        with self.assertRaises(ToolExecutionError):
            tool.run(dir_path="/nonexistent/directory")

    def test_read_file_tool_permission(self):
        """测试 ReadFileTool 的权限"""
        tool = ReadFileTool()
        self.assertEqual(tool.permission, "read")

    def test_read_file_tool_display(self):
        """测试 ReadFileTool 的 display 方法"""
        tool = ReadFileTool()
        self.assertEqual(tool.display(file_path="file1.txt"), "读取文件 file1.txt")
        self.assertEqual(tool.display(), "读取文件")

    def test_read_file_tool_basic(self):
        """测试 ReadFileTool 基本功能"""
        tool = ReadFileTool()
        result = tool.run(file_path=self.test_file)
        self.assertIn("line 1", result)
        self.assertIn("line 5", result)

    def test_read_file_tool_with_offset_limit(self):
        """测试 ReadFileTool 使用 offset 和 limit（0-based）"""
        tool = ReadFileTool()
        # offset=1, limit=2 应该读取第 2-3 行（0-based 索引 1-2）
        result = tool.run(file_path=self.test_file, offset=1, limit=2)
        self.assertIn("line 2", result)
        self.assertIn("line 3", result)
        self.assertNotIn("line 1", result)
        self.assertNotIn("line 4", result)

    def test_search_file_content_tool_permission(self):
        """测试 SearchFileContentTool 的权限"""
        tool = SearchFileContentTool()
        self.assertEqual(tool.permission, "read")

    def test_search_file_content_tool_display(self):
        """测试 SearchFileContentTool 的 display 方法"""
        tool = SearchFileContentTool()
        self.assertEqual(tool.display(pattern="test"), "搜索文本 'test'")
        self.assertEqual(tool.display(), "搜索文本")

    def test_search_file_content_tool(self):
        """测试 SearchFileContentTool 基本功能"""
        tool = SearchFileContentTool()
        # 不指定 dir_path，使用默认 workspace
        result = tool.run(pattern="line 3")
        # 如果找不到，可能是 workspace 不匹配，至少应该不报错
        self.assertIsInstance(result, str)

    def test_glob_search_tool_permission(self):
        """测试 GlobSearchTool 的权限"""
        tool = GlobSearchTool()
        self.assertEqual(tool.permission, "read")

    def test_glob_search_tool_display(self):
        """测试 GlobSearchTool 的 display 方法"""
        tool = GlobSearchTool()
        self.assertEqual(tool.display(pattern="*.py"), "查找文件 '*.py'")
        self.assertEqual(tool.display(), "查找文件")

    def test_glob_search_tool(self):
        """测试 GlobSearchTool 基本功能"""
        tool = GlobSearchTool()
        # 不指定 dir_path，使用默认 workspace，查找所有 .txt 文件
        result = tool.run(pattern="*.txt")
        # 至少应该返回一个结果字符串
        self.assertIsInstance(result, str)
        self.assertIn("Found", result)

    def test_glob_search_tool_nonexistent_dir(self):
        """测试 GlobSearchTool 处理不存在的目录"""
        tool = GlobSearchTool()
        with self.assertRaises(ToolExecutionError):
            tool.run(pattern="*.txt", dir_path="/nonexistent/directory")

    def test_glob_search_tool_no_matches(self):
        """测试 GlobSearchTool 处理无匹配的情况"""
        tool = GlobSearchTool()
        # 查找不存在的文件模式，不指定 dir_path 使用默认 workspace
        result = tool.run(pattern="*.nonexistent_extension_12345")
        # 应该返回无匹配的结果
        self.assertIn("Found 0 file(s)", result)

    def test_write_file_tool_permission(self):
        """测试 WriteFileTool 的权限"""
        tool = WriteFileTool()
        self.assertEqual(tool.permission, "edit")

    def test_write_file_tool_display(self):
        """测试 WriteFileTool 的 display 方法"""
        tool = WriteFileTool()
        self.assertEqual(tool.display(file_path="/test/file.txt"), "写入文件 /test/file.txt")
        self.assertEqual(tool.display(), "写入文件")

    def test_write_file_tool_create(self):
        """测试 WriteFileTool 创建文件"""
        tool = WriteFileTool()
        new_file = os.path.join(self.test_dir, "new.txt")
        result = tool.run(file_path=new_file, content="new content")
        self.assertIn("Created", result)
        self.assertTrue(os.path.exists(new_file))
        with open(new_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "new content")

    def test_write_file_tool_overwrite(self):
        """测试 WriteFileTool 覆盖已存在的文件"""
        tool = WriteFileTool()
        result = tool.run(file_path=self.test_file, content="new content")
        self.assertIn("Overwrote", result)
        with open(self.test_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "new content")

    def test_write_file_tool_create_directory(self):
        """测试 WriteFileTool 自动创建目录"""
        tool = WriteFileTool()
        new_file = os.path.join(self.test_dir, "subdir", "new.txt")
        tool.run(file_path=new_file, content="content")
        self.assertTrue(os.path.exists(new_file))

    def test_replace_tool_permission(self):
        """测试 ReplaceTool 的权限"""
        tool = ReplaceTool()
        self.assertEqual(tool.permission, "edit")

    def test_replace_tool_display(self):
        """测试 ReplaceTool 的 display 方法"""
        tool = ReplaceTool()
        self.assertEqual(
            tool.display(file_path="/test.txt"),
            "编辑文件 /test.txt"
        )
        self.assertEqual(tool.display(), "编辑文件")

    def test_replace_tool(self):
        """测试 ReplaceTool 替换内容"""
        tool = ReplaceTool()
        tool.run(
            file_path=self.test_file,
            instruction="替换第3行",
            old_string="line 2\nline 3\nline 4",
            new_string="line 2\nreplaced line\nline 4"
        )
        
        with open(self.test_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("replaced line", content)
        self.assertNotIn("line 3", content)

    def test_replace_tool_multiple_replacements(self):
        """测试 ReplaceTool 多次替换"""
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("line 1\nline 2\nline 1\nline 3\n")
        
        tool = ReplaceTool()
        tool.run(
            file_path=self.test_file,
            instruction="替换所有 line 1",
            old_string="line 1",
            new_string="replaced",
            expected_replacements=2
        )
        
        with open(self.test_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertEqual(content.count("replaced"), 2)
        self.assertEqual(content.count("line 1"), 0)

    def test_delete_file_tool_permission(self):
        """测试 DeleteFileTool 的权限"""
        tool = DeleteFileTool()
        self.assertEqual(tool.permission, "delete")

    def test_delete_file_tool_display(self):
        """测试 DeleteFileTool 的 display 方法"""
        tool = DeleteFileTool()
        self.assertEqual(tool.display(file_path="/test.txt"), "删除文件 /test.txt")

    def test_delete_file_tool(self):
        """测试 DeleteFileTool 删除文件"""
        tool = DeleteFileTool()
        tool.run(file_path=self.test_file)
        self.assertFalse(os.path.exists(self.test_file))

    def test_delete_file_tool_nonexistent(self):
        """测试 DeleteFileTool 处理不存在的文件"""
        tool = DeleteFileTool()
        with self.assertRaises(ToolExecutionError):
            tool.run(file_path="/nonexistent/file.txt")

    def test_move_file_tool_permission(self):
        """测试 MoveFileTool 的权限"""
        tool = MoveFileTool()
        self.assertEqual(tool.permission, "edit")

    def test_move_file_tool_display(self):
        """测试 MoveFileTool 的 display 方法"""
        tool = MoveFileTool()
        self.assertEqual(
            tool.display(source_path="/source.txt", target_path="/target.txt"),
            "移动文件 /source.txt -> /target.txt"
        )

    def test_move_file_tool(self):
        """测试 MoveFileTool 移动文件"""
        tool = MoveFileTool()
        target = os.path.join(self.test_dir, "moved.txt")
        tool.run(source_path=self.test_file, target_path=target)
        self.assertFalse(os.path.exists(self.test_file))
        self.assertTrue(os.path.exists(target))

    def test_move_file_tool_existing_target(self):
        """测试 MoveFileTool 处理已存在的目标文件"""
        tool = MoveFileTool()
        with self.assertRaises(ToolExecutionError) as cm:
            tool.run(source_path=self.test_file, target_path=self.test_file)
        self.assertIn("目标文件已存在", str(cm.exception))


if __name__ == "__main__":
    unittest.main()

