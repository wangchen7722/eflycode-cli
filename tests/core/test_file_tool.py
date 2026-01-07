import os
import tempfile
import unittest

from eflycode.core.tool.errors import ToolExecutionError
from eflycode.core.tool.file_tool import (
    CreateFileTool,
    DeleteFileContentTool,
    DeleteFileTool,
    GrepSearchTool,
    InsertFileContentTool,
    ListFilesTool,
    MoveFileTool,
    ReadFileTool,
    ReplaceEditFileTool,
)


class TestFileTools(unittest.TestCase):
    """文件操作工具测试类"""

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

    def test_list_files_tool_permission(self):
        """测试 ListFilesTool 的权限"""
        tool = ListFilesTool()
        self.assertEqual(tool.permission, "read")

    def test_list_files_tool_display(self):
        """测试 ListFilesTool 的 display 方法"""
        tool = ListFilesTool()
        self.assertEqual(tool.display(directory="/test"), "列出目录 /test")
        self.assertEqual(tool.display(), "列出目录")

    def test_list_files_tool(self):
        """测试 ListFilesTool 功能"""
        tool = ListFilesTool()
        result = tool.run(directory=self.test_dir)
        self.assertIn("test.txt", result)
        self.assertIn("(5 lines)", result)

    def test_list_files_tool_nonexistent(self):
        """测试 ListFilesTool 处理不存在的目录"""
        tool = ListFilesTool()
        with self.assertRaises(ToolExecutionError):
            tool.run(directory="/nonexistent/directory")

    def test_read_file_tool_permission(self):
        """测试 ReadFileTool 的权限"""
        tool = ReadFileTool()
        self.assertEqual(tool.permission, "read")

    def test_read_file_tool_display(self):
        """测试 ReadFileTool 的 display 方法"""
        tool = ReadFileTool()
        self.assertEqual(tool.display(files=["file1.txt"]), "读取 file1.txt")
        self.assertEqual(
            tool.display(files=[{"path": "file1.txt", "start_line": 1, "end_line": 10}]),
            "读取 file1.txt (1行-10行)"
        )
        self.assertEqual(
            tool.display(files=[{"path": "file1.txt", "start_line": 30, "line_count": 20}]),
            "读取 file1.txt (30行-49行)"
        )
        self.assertEqual(
            tool.display(files=[{"path": "file1.txt", "start_line": 5}]),
            "读取 file1.txt (从5行开始)"
        )

    def test_read_file_tool_basic(self):
        """测试 ReadFileTool 基本功能"""
        tool = ReadFileTool()
        result = tool.run(files=[self.test_file])
        self.assertIn("line 1", result)
        self.assertIn("line 5", result)

    def test_read_file_tool_with_range(self):
        """测试 ReadFileTool 指定行号范围"""
        tool = ReadFileTool()
        result = tool.run(files=[{"path": self.test_file, "start_line": 2, "end_line": 4}])
        self.assertIn("line 2", result)
        self.assertIn("line 3", result)
        self.assertIn("line 4", result)
        self.assertNotIn("line 1", result)
        self.assertNotIn("line 5", result)

    def test_read_file_tool_with_line_count(self):
        """测试 ReadFileTool 指定行数"""
        tool = ReadFileTool()
        result = tool.run(files=[{"path": self.test_file, "start_line": 2, "line_count": 2}])
        self.assertIn("line 2", result)
        self.assertIn("line 3", result)
        self.assertNotIn("line 1", result)
        self.assertNotIn("line 4", result)

    def test_read_file_tool_with_line_numbers(self):
        """测试 ReadFileTool 显示行号"""
        tool = ReadFileTool()
        result = tool.run(files=[self.test_file], show_line_numbers=True)
        self.assertIn("   1 |", result)
        self.assertIn("   5 |", result)

    def test_read_file_tool_multiple_files(self):
        """测试 ReadFileTool 读取多个文件"""
        with open(self.test_file2, "w", encoding="utf-8") as f:
            f.write("file2 line 1\nfile2 line 2\n")
        
        tool = ReadFileTool()
        result = tool.run(files=[self.test_file, self.test_file2])
        self.assertIn("test.txt", result)
        self.assertIn("test2.txt", result)
        self.assertIn("line 1", result)
        self.assertIn("file2 line 1", result)

    def test_grep_search_tool_permission(self):
        """测试 GrepSearchTool 的权限"""
        tool = GrepSearchTool()
        self.assertEqual(tool.permission, "read")

    def test_grep_search_tool_display(self):
        """测试 GrepSearchTool 的 display 方法"""
        tool = GrepSearchTool()
        self.assertEqual(tool.display(pattern="test", path="/path"), "搜索 /path 中的 'test'")
        self.assertEqual(tool.display(pattern="test"), "搜索 'test'")
        self.assertEqual(tool.display(path="/path"), "搜索 /path")

    def test_grep_search_tool(self):
        """测试 GrepSearchTool 基本功能"""
        tool = GrepSearchTool()
        result = tool.run(pattern="line 3", path=self.test_file)
        self.assertIn("line 3", result)
        self.assertIn("test.txt:3:", result)

    def test_grep_search_tool_ignore_case(self):
        """测试 GrepSearchTool 忽略大小写"""
        tool = GrepSearchTool()
        result = tool.run(pattern="LINE", path=self.test_file, ignore_case=True)
        self.assertIn("line", result)

    def test_grep_search_tool_max_count(self):
        """测试 GrepSearchTool 最大匹配数限制"""
        tool = GrepSearchTool()
        result = tool.run(pattern="line", path=self.test_file, max_count=2)
        self.assertIn("[已达到最大匹配行数限制: 2]", result)

    def test_create_file_tool_permission(self):
        """测试 CreateFileTool 的权限"""
        tool = CreateFileTool()
        self.assertEqual(tool.permission, "edit")

    def test_create_file_tool_display(self):
        """测试 CreateFileTool 的 display 方法"""
        tool = CreateFileTool()
        self.assertEqual(tool.display(filepath="/test/file.txt"), "创建文件 /test/file.txt")
        self.assertEqual(tool.display(), "创建文件")

    def test_create_file_tool(self):
        """测试 CreateFileTool 创建文件"""
        tool = CreateFileTool()
        new_file = os.path.join(self.test_dir, "new.txt")
        result = tool.run(filepath=new_file, content="new content")
        self.assertIn("创建成功", result)
        self.assertTrue(os.path.exists(new_file))
        with open(new_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "new content")

    def test_create_file_tool_existing_file(self):
        """测试 CreateFileTool 处理已存在的文件"""
        tool = CreateFileTool()
        with self.assertRaises(ToolExecutionError) as cm:
            tool.run(filepath=self.test_file, content="content")
        self.assertIn("文件已存在", str(cm.exception))

    def test_create_file_tool_create_directory(self):
        """测试 CreateFileTool 自动创建目录"""
        tool = CreateFileTool()
        new_file = os.path.join(self.test_dir, "subdir", "new.txt")
        tool.run(filepath=new_file, content="content")
        self.assertTrue(os.path.exists(new_file))

    def test_insert_file_content_tool_permission(self):
        """测试 InsertFileContentTool 的权限"""
        tool = InsertFileContentTool()
        self.assertEqual(tool.permission, "edit")

    def test_insert_file_content_tool_display(self):
        """测试 InsertFileContentTool 的 display 方法"""
        tool = InsertFileContentTool()
        self.assertEqual(
            tool.display(file_path="/test.txt", line_number=5),
            "在 /test.txt 第 5 行插入内容"
        )
        self.assertEqual(tool.display(file_path="/test.txt"), "在 /test.txt 插入内容")

    def test_insert_file_content_tool(self):
        """测试 InsertFileContentTool 插入内容"""
        tool = InsertFileContentTool()
        tool.run(file_path=self.test_file, content="inserted line", line_number=3)
        
        with open(self.test_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        self.assertEqual(lines[2].strip(), "inserted line")
        self.assertEqual(lines[3].strip(), "line 3")

    def test_replace_edit_file_tool_permission(self):
        """测试 ReplaceEditFileTool 的权限"""
        tool = ReplaceEditFileTool()
        self.assertEqual(tool.permission, "edit")

    def test_replace_edit_file_tool_display(self):
        """测试 ReplaceEditFileTool 的 display 方法"""
        tool = ReplaceEditFileTool()
        self.assertEqual(
            tool.display(file_path="/test.txt"),
            "替换 /test.txt 中的内容"
        )

    def test_replace_edit_file_tool(self):
        """测试 ReplaceEditFileTool 替换内容"""
        tool = ReplaceEditFileTool()
        tool.run(
            file_path=self.test_file,
            old_content="line 3\n",
            new_content="replaced line\n"
        )
        
        with open(self.test_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("replaced line", content)
        self.assertNotIn("line 3", content)

    def test_replace_edit_file_tool_multiple_matches(self):
        """测试 ReplaceEditFileTool 处理多个匹配"""
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("line 1\nline 2\nline 1\nline 3\n")
        
        tool = ReplaceEditFileTool()
        with self.assertRaises(ToolExecutionError) as cm:
            tool.run(
                file_path=self.test_file,
                old_content="line 1\n",
                new_content="replaced\n"
            )
        self.assertIn("出现", str(cm.exception))
        self.assertIn("次", str(cm.exception))

    def test_delete_file_content_tool_permission(self):
        """测试 DeleteFileContentTool 的权限"""
        tool = DeleteFileContentTool()
        self.assertEqual(tool.permission, "delete")

    def test_delete_file_content_tool_display(self):
        """测试 DeleteFileContentTool 的 display 方法"""
        tool = DeleteFileContentTool()
        self.assertEqual(
            tool.display(file_path="/test.txt", start_line=5, end_line=10),
            "删除 /test.txt 第 5-10 行"
        )
        self.assertEqual(
            tool.display(file_path="/test.txt", start_line=5),
            "删除 /test.txt 第 5 行"
        )

    def test_delete_file_content_tool_single_line(self):
        """测试 DeleteFileContentTool 删除单行"""
        tool = DeleteFileContentTool()
        tool.run(file_path=self.test_file, start_line=3)
        
        with open(self.test_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 4)
        self.assertNotIn("line 3", "".join(lines))

    def test_delete_file_content_tool_range(self):
        """测试 DeleteFileContentTool 删除行范围"""
        tool = DeleteFileContentTool()
        tool.run(file_path=self.test_file, start_line=2, end_line=4)
        
        with open(self.test_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("line 1", lines[0])
        self.assertIn("line 5", lines[1])

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
        with self.assertRaises(ToolExecutionError) as cm:
            tool.run(file_path="/nonexistent/file.txt")
        self.assertIn("文件不存在", str(cm.exception))

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

