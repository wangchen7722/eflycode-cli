#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试file_tool模块
"""

import os
import tempfile
import shutil
import unittest
from pathlib import Path

from echo.tool.file.file_tool import ListFilesTool
from echo.tool.schema import ToolParameterError


class TestListFilesTool(unittest.TestCase):
    """测试ListFilesTool工具"""
    
    def setUp(self):
        """每个测试方法前的设置"""
        self.tool = ListFilesTool()
        # 创建临时测试目录
        self.test_dir = tempfile.mkdtemp()
        self.test_files = [
            "file1.txt",
            "file2.py",
            "README.md",
            # 应该被基本过滤忽略
            "__pycache__/cache.pyc",
            # 应该被基本过滤忽略
            "node_modules/package.json",
            # 应该被基本过滤忽略
            ".hidden_file",
            "subdir/file3.txt",
            "subdir/file4.py",
            "subdir/nested/file5.txt",
            # 可能被.echoignore忽略
            "logs/app.log",
            # 可能被.echoignore忽略
            "data/model.pkl",
        ]
        
        # 创建测试文件和目录
        for file_path in self.test_files:
            full_path = Path(self.test_dir) / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(f"Content of {file_path}")
        
        # 创建测试用的.echoignore文件
        echoignore_content = """
# 测试忽略规则
*.log
logs/
data/
*.pkl
*.pyc
        """.strip()
        
        echoignore_path = Path(self.test_dir) / ".echoignore"
        echoignore_path.write_text(echoignore_content)
    
    def tearDown(self):
        """每个测试方法后的清理"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_tool_properties(self):
        """测试工具基本属性"""
        self.assertEqual(self.tool.name, "list_files")
        self.assertEqual(self.tool.type, "function")
        self.assertEqual(self.tool.should_approval, False)
        self.assertIn("查看指定目录中的文件和目录", self.tool.description)
        self.assertIn("apply_ignore", str(self.tool.parameters))
    
    def test_list_files_non_recursive(self):
        """测试非递归列出文件"""
        result = self.tool.do_run(self.test_dir, recursive=False, apply_ignore=False)
        
        self.assertIn("成功查看", result)
        self.assertIn("file1.txt", result)
        self.assertIn("file2.py", result)
        self.assertIn("README.md", result)
        # 目录应该被列出
        self.assertIn("subdir", result)
        
        # 在不应用忽略规则时，隐藏文件和缓存目录会被显示
        self.assertIn(".hidden_file", result)
        self.assertIn("__pycache__", result)
        self.assertIn("node_modules", result)
        
        # 子目录中的文件不应该出现（非递归）
        self.assertNotIn("file3.txt", result)
        self.assertNotIn("file4.py", result)
    
    def test_list_files_recursive(self):
        """测试递归列出文件"""
        result = self.tool.do_run(self.test_dir, recursive=True, apply_ignore=False)
        
        self.assertIn("成功递归查看", result)
        self.assertIn("最大深度2", result)
        
        # 顶级文件
        self.assertIn("file1.txt", result)
        self.assertIn("file2.py", result)
        self.assertIn("README.md", result)
        
        # 子目录中的文件
        self.assertIn("subdir/file3.txt", result)
        self.assertIn("subdir/file4.py", result)
        self.assertIn("subdir/nested/file5.txt", result)
        
        # 在不应用忽略规则时，隐藏文件和缓存目录会被显示
        self.assertIn(".hidden_file", result)
        self.assertIn("__pycache__", result)
        self.assertIn("node_modules", result)
    
    def test_list_files_with_ignore_rules(self):
        """测试应用忽略规则"""
        result = self.tool.do_run(self.test_dir, recursive=True, apply_ignore=True)
        
        self.assertIn("成功递归查看", result)
        self.assertIn("应用忽略规则", result)
        
        # 正常文件应该存在
        self.assertIn("file1.txt", result)
        self.assertIn("file2.py", result)
        self.assertIn("README.md", result)
        self.assertIn("subdir/file3.txt", result)
        self.assertIn("subdir/file4.py", result)
        
        # 被忽略规则匹配的文件不应该出现
        self.assertNotIn("logs/app.log", result)
        self.assertNotIn("data/model.pkl", result)
        self.assertNotIn("cache.pyc", result)
    
    def test_list_files_non_recursive_with_ignore(self):
        """测试非递归模式下应用忽略规则"""
        result = self.tool.do_run(self.test_dir, recursive=False, apply_ignore=True)
        
        self.assertIn("成功查看", result)
        self.assertIn("应用忽略规则", result)
        
        # 正常文件应该存在
        self.assertIn("file1.txt", result)
        self.assertIn("file2.py", result)
        self.assertIn("README.md", result)
        
        # 被忽略的目录不应该出现
        self.assertNotIn("logs", result)
        self.assertNotIn("data", result)
    
    def test_invalid_directory(self):
        """测试无效目录"""
        with self.assertRaises(ToolParameterError) as context:
            self.tool.do_run("/nonexistent/directory")
        
        self.assertIn("未找到目录", str(context.exception))
    
    def test_not_a_directory(self):
        """测试路径不是目录"""
        # 创建一个文件
        test_file = Path(self.test_dir) / "test_file.txt"
        test_file.write_text("test content")
        
        with self.assertRaises(ToolParameterError) as context:
            self.tool.do_run(str(test_file))
        
        self.assertIn("不是一个目录", str(context.exception))
    
    def test_empty_directory(self):
        """测试空目录"""
        empty_dir = Path(self.test_dir) / "empty"
        empty_dir.mkdir()
        
        result = self.tool.do_run(str(empty_dir), recursive=False, apply_ignore=False)
        
        self.assertIn("成功查看", result)
        # 空目录应该只显示标题，没有文件列表
        lines = result.split('\n')
        self.assertLessEqual(len(lines), 2)  # 标题行 + 可能的空行
    
    def test_max_depth_limit(self):
        """测试最大深度限制"""
        # 创建超过2层深度的目录结构，在每一层都创建文件
        level1_path = Path(self.test_dir) / "level1"
        level1_path.mkdir()
        (level1_path / "file1.txt").write_text("level1 content")
        
        level2_path = level1_path / "level2"
        level2_path.mkdir()
        (level2_path / "file2.txt").write_text("level2 content")
        
        level3_path = level2_path / "level3"
        level3_path.mkdir()
        (level3_path / "file3.txt").write_text("level3 content")
        
        level4_path = level3_path / "level4"
        level4_path.mkdir()
        (level4_path / "deep_file.txt").write_text("level4 content")
        
        result = self.tool.do_run(self.test_dir, recursive=True, apply_ignore=False)
        
        # 第4层的文件不应该出现（超过最大深度3）
        self.assertNotIn("level4/deep_file.txt", result)
        self.assertNotIn("level1/level2/level3/level4/deep_file.txt", result)
        
        # 但是前3层的文件应该存在
        self.assertTrue("level1/file1.txt" in result or "level1/level2/file2.txt" in result or "level1/level2/level3/file3.txt" in result)
    
    def test_permission_error_handling(self):
        """测试权限错误处理（模拟）"""
        # 这个测试可能需要特殊的环境设置，暂时跳过
        # 在实际环境中，可以通过修改目录权限来测试
        pass
    
    def test_display_method(self):
        """测试display方法"""
        display_text = self.tool.display()
        self.assertEqual(display_text, "查看文件和目录列表")
    
    def test_examples_property(self):
        """测试examples属性"""
        examples = self.tool.examples
        self.assertIsInstance(examples, dict)
        self.assertGreater(len(examples), 0)
        
        # 检查示例的结构
        for example_name, example_data in examples.items():
            self.assertIn("type", example_data)
            self.assertIn("name", example_data)
            self.assertIn("arguments", example_data)
            self.assertEqual(example_data["name"], "list_files")


if __name__ == "__main__":
    # 运行测试
    unittest.main(verbosity=2)