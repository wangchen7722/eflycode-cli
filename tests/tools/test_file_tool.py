import os
import shutil
import tempfile
import unittest

from echoai.cli.tools.file_tool import (
    CreateFileTool,
    EditFileTool,
    ListFilesTool,
    ReadFileTool,
    SearchFilesTool,
)


class FileToolTestBase(unittest.TestCase):
    def setUp(self):
        """创建临时目录"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file = os.path.join(self.temp_dir, "test.txt")
        content = "Line 1\nLine 2\nLine 3\n"
        with open(self.temp_file, "w", encoding="utf-8") as f:
            f.write(content)

        # 创建嵌套的临时目录结构
        self.nested_temp_dir = self.temp_dir
        self.sub_dir = os.path.join(self.temp_dir, "subdir")
        os.makedirs(self.sub_dir)
        
        # 在根目录和子目录中创建文件
        files = [
            (os.path.join(self.temp_dir, "root.txt"), "root content"),
            (os.path.join(self.sub_dir, "sub.txt"), "sub content"),
            (os.path.join(self.sub_dir, "test.py"), "print('test')")
        ]
        
        for path, content in files:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

    def tearDown(self):
        """清理临时目录"""
        shutil.rmtree(self.temp_dir)

class TestListFilesTool(FileToolTestBase):
    def test_list_files_non_recursive(self):
        tool = ListFilesTool()
        result = tool.run(self.nested_temp_dir, recursive=False)
        self.assertIn("Successfully listed", result)
        self.assertIn("root.txt", result)
        self.assertIn("subdir", result)
    
    def test_list_files_recursive(self):
        tool = ListFilesTool()
        result = tool.run(self.nested_temp_dir, recursive=True)
        self.assertIn("Successfully listed", result)
        self.assertIn("root.txt", result)
        self.assertIn("subdir/sub.txt", result)
        self.assertIn("subdir/test.py", result)
    
    def test_list_files_non_existent_dir(self):
        tool = ListFilesTool()
        result = tool.run("non_existent_dir")
        self.assertIn("ERROR: Directory not found", result)
    
    def test_list_files_not_a_dir(self):
        tool = ListFilesTool()
        result = tool.run(self.temp_file)
        self.assertIn("is not a directory. Please ensure the path points to a directory", result)

class TestReadFileTool(FileToolTestBase):
    def test_read_file_entire(self):
        tool = ReadFileTool()
        result = tool.run(self.temp_file)
        self.assertIn("Line 1", result)
        self.assertIn("Line 2", result)
        self.assertIn("Line 3", result)
    
    def test_read_file_with_range(self):
        tool = ReadFileTool()
        result = tool.run(self.temp_file, start_line=2, end_line=2)
        self.assertNotIn("Line 1", result)
        self.assertIn("Line 2", result)
        self.assertNotIn("Line 3", result)
    
    def test_read_file_non_existent(self):
        tool = ReadFileTool()
        result = tool.run("non_existent.txt")
        self.assertIn("ERROR: File not found", result)
    
    def test_read_file_invalid_range(self):
        tool = ReadFileTool()
        result = tool.run(self.temp_file, start_line=10, end_line=20)
        self.assertIn("ERROR: end_line must be between", result)

class TestSearchFilesTool(FileToolTestBase):
    def test_search_files_basic(self):
        tool = SearchFilesTool()
        result = tool.run(self.nested_temp_dir, regex="test", pattern="*.py")
        self.assertIn("test", result)
    
    def test_search_files_no_matches(self):
        tool = SearchFilesTool()
        result = tool.run(self.nested_temp_dir, regex="nonexistent", pattern="*.txt")
        self.assertIn("No matches found", result)
    
    def test_search_files_invalid_regex(self):
        tool = SearchFilesTool()
        result = tool.run(self.nested_temp_dir, regex="[", pattern="*.txt")
        self.assertIn("ERROR: Invalid regular expression pattern", result)
    
    def test_search_files_non_existent_dir(self):
        tool = SearchFilesTool()
        result = tool.run("non_existent_dir", regex="test")
        self.assertIn("ERROR: Directory not found", result)

class TestCreateFileTool(FileToolTestBase):
    def test_create_file_success(self):
        tool = CreateFileTool()
        file_path = os.path.join(self.temp_dir, "new.txt")
        content = "test content"
        result = tool.run(file_path, content)
        self.assertIn("Successfully created file", result)
        self.assertTrue(os.path.exists(file_path))
        with open(file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), content)
    
    def test_create_file_already_exists(self):
        tool = CreateFileTool()
        result = tool.run(self.temp_file, "new content")
        self.assertIn("ERROR: File already exists", result)

class TestUpdateFileTool(FileToolTestBase):
    def test_update_file_success(self):
        tool = EditFileTool()
        with open(self.temp_file, "r", encoding="utf-8") as f:
            old_content = f.read()
        result = tool.run(self.temp_file, old_content, "Updated content")
        self.assertIn("Successfully replaced", result)
        with open(self.temp_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "Updated content")
    
    def test_update_file_non_existent(self):
        tool = EditFileTool()
        result = tool.run("non_existent.txt", "old", "new")
        self.assertIn("ERROR: File not found", result)
    
    def test_update_file_no_match(self):
        tool = EditFileTool()
        result = tool.run(self.temp_file, "nonexistent content", "new content")
        self.assertIn("ERROR: 'nonexistent content' not found", result)
    
    def test_update_file_multiple_matches(self):
        # 创建包含重复内容的文件
        file_path = os.path.join(self.temp_dir, "duplicate.txt")
        content = "test\ntest\n"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        tool = EditFileTool()
        result = tool.run(file_path, "test", "updated")
        self.assertIn("ERROR: Found 2 instances", result)
    
    def test_create_new_file_with_update_tool(self):
        tool = EditFileTool()
        file_path = os.path.join(self.temp_dir, "created.txt")
        result = tool.run(file_path, "", "new content")
        self.assertIn("Successfully created new file", result)
        self.assertTrue(os.path.exists(file_path))
        with open(file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "new content")

if __name__ == '__main__':
    unittest.main()