#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import tempfile
import unittest
from unittest.mock import patch

from echo.tool.file.file_tool import EditFileTool
from echo.tool.base_tool import ToolParameterError


class TestEditFileTool(unittest.TestCase):
    def setUp(self):
        """设置测试环境"""
        self.tool = EditFileTool()
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.txt")
        
        # 创建测试文件
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("第一行\n第二行\n第三行\n")
    
    def tearDown(self):
        """清理测试环境"""
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        os.rmdir(self.temp_dir)
    
    def test_search_replace_mode(self):
        """测试搜索替换模式"""
        result = self.tool.run(
            path=self.test_file,
            old_string="第二行",
            new_string="修改后的第二行"
        )
        
        self.assertIn("成功", result)
        
        # 验证文件内容
        with open(self.test_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        self.assertIn("修改后的第二行", content)
        self.assertNotIn("第二行", content.replace("修改后的第二行", ""))
    
    def test_insert_mode(self):
        """测试插入模式"""
        result = self.tool.run(
            path=self.test_file,
            old_string="",
            new_string="插入的新行",
            line_number=2
        )
        
        self.assertIn("成功", result)
        self.assertIn("第 2 行插入", result)
        
        # 验证文件内容
        with open(self.test_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        self.assertEqual(lines[1].strip(), "插入的新行")
        self.assertEqual(len(lines), 4)  # 原来3行，插入1行
    
    def test_insert_at_end(self):
        """测试在文件末尾插入"""
        result = self.tool.run(
            path=self.test_file,
            old_string="",
            new_string="末尾新行",
            line_number=4
        )
        
        self.assertIn("成功", result)
        
        # 验证文件内容
        with open(self.test_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        self.assertEqual(lines[-1].strip(), "末尾新行")
    
    def test_insert_without_line_number(self):
        """测试插入模式但未提供行号"""
        with self.assertRaises(ToolParameterError) as context:
            self.tool.run(
                path=self.test_file,
                old_string="",
                new_string="新内容"
            )
        
        self.assertIn("插入模式需要指定line_number参数", str(context.exception))
    
    def test_invalid_line_number(self):
        """测试无效的行号"""
        with self.assertRaises(ToolParameterError) as context:
            self.tool.run(
                path=self.test_file,
                old_string="",
                new_string="新内容",
                line_number=10  # 超出范围
            )
        
        self.assertIn("行号必须在", str(context.exception))
    
    def test_old_string_not_found(self):
        """测试搜索字符串不存在"""
        with self.assertRaises(ToolParameterError) as context:
            self.tool.run(
                path=self.test_file,
                old_string="不存在的内容",
                new_string="新内容"
            )
        
        self.assertIn("未找到", str(context.exception))
    
    def test_multiple_matches(self):
        """测试多个匹配项"""
        # 创建包含重复内容的文件
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("重复\n重复\n不同\n")
        
        with self.assertRaises(ToolParameterError) as context:
            self.tool.run(
                path=self.test_file,
                old_string="重复",
                new_string="新内容"
            )
        
        self.assertIn("找到 2 个", str(context.exception))
        self.assertIn("唯一存在", str(context.exception))
    
    def test_file_not_found(self):
        """测试文件不存在"""
        non_existent_file = os.path.join(self.temp_dir, "non_existent.txt")
        
        with self.assertRaises(ToolParameterError) as context:
            self.tool.run(
                path=non_existent_file,
                old_string="内容",
                new_string="新内容"
            )
        
        self.assertIn("文件未找到", str(context.exception))
    
    def test_path_is_directory(self):
        """测试路径是目录而不是文件"""
        with self.assertRaises(ToolParameterError) as context:
            self.tool.run(
                path=self.temp_dir,
                old_string="内容",
                new_string="新内容"
            )
        
        self.assertIn("不是一个文件", str(context.exception))


if __name__ == "__main__":
    unittest.main()