#!/usr/bin/env python3
"""
FileWatcher 哈希功能测试

使用 unittest 框架测试程序修改和用户修改的区分功能
"""

import os
import time
import tempfile
import unittest
from pathlib import Path
from eflycode.util.file_watcher import FileWatcher


class TestFileWatcher(unittest.TestCase):
    """FileWatcher 测试类"""
    
    def setUp(self):
        """测试前的准备工作"""
        # 创建临时测试文件
        self.temp_file = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt")
        self.test_file = self.temp_file.name
        self.temp_file.write("初始内容")
        self.temp_file.close()
        
        # 创建 FileWatcher 实例
        self.watcher = FileWatcher()
        
        # 记录回调触发次数
        self.callback_count = 0
        self.callback_messages = []
        
        # 添加文件监听
        self.watcher.add_file(self.test_file, self._file_changed_callback)
    
    def tearDown(self):
        """测试后的清理工作"""
        # 移除文件监听
        self.watcher.remove_file(self.test_file)
        
        # 删除临时文件
        if os.path.exists(self.test_file):
            os.unlink(self.test_file)
    
    def _file_changed_callback(self, file_path):
        """文件变化回调函数"""
        self.callback_count += 1
        message = f"回调触发 #{self.callback_count}: 文件 {file_path} 被用户修改"
        self.callback_messages.append(message)
    
    def test_programmatic_change_detection(self):
        """测试程序修改检测"""
        # 程序修改：先设置预期哈希，再修改文件
        new_content = "程序修改的内容"
        
        # 设置预期哈希
        self.watcher.set_expected_hash_for_content(self.test_file, new_content)
        
        # 修改文件
        with open(self.test_file, "w") as f:
            f.write(new_content)
        
        # 检查是否正确识别为程序修改
        is_programmatic = self.watcher._is_programmatic_change(self.test_file)
        self.assertTrue(is_programmatic, "应该识别为程序修改")
        
        # 更新哈希（模拟程序修改流程）
        self.watcher._update_file_hash(self.test_file)
        
        # 验证没有触发回调
        self.assertEqual(self.callback_count, 0, "程序修改不应该触发回调")
    
    def test_user_change_detection(self):
        """测试用户修改检测"""
        # 用户修改：直接修改文件，不设置预期哈希
        user_content = "用户修改的内容"
        
        # 直接修改文件
        with open(self.test_file, "w") as f:
            f.write(user_content)
        
        # 检查是否正确识别为用户修改
        is_programmatic = self.watcher._is_programmatic_change(self.test_file)
        self.assertFalse(is_programmatic, "应该识别为用户修改")
        
        # 触发回调（模拟用户修改流程）
        self.watcher._trigger_callbacks(self.test_file)
        
        # 验证触发了回调
        self.assertEqual(self.callback_count, 1, "用户修改应该触发回调")
        self.assertIn("被用户修改", self.callback_messages[0])
    
    def test_multiple_changes(self):
        """测试多次修改的混合场景"""
        initial_callback_count = self.callback_count
        
        # 第一次：程序修改
        content1 = "程序第一次修改"
        self.watcher.set_expected_hash_for_content(self.test_file, content1)
        with open(self.test_file, "w") as f:
            f.write(content1)
        
        if self.watcher._is_programmatic_change(self.test_file):
            self.watcher._update_file_hash(self.test_file)
        else:
            self.watcher._trigger_callbacks(self.test_file)
        
        # 第二次：用户修改
        content2 = "用户第一次修改"
        with open(self.test_file, "w") as f:
            f.write(content2)
        
        if self.watcher._is_programmatic_change(self.test_file):
            self.watcher._update_file_hash(self.test_file)
        else:
            self.watcher._trigger_callbacks(self.test_file)
        
        # 第三次：程序修改
        content3 = "程序第二次修改"
        self.watcher.set_expected_hash_for_content(self.test_file, content3)
        with open(self.test_file, "w") as f:
            f.write(content3)
        
        if self.watcher._is_programmatic_change(self.test_file):
            self.watcher._update_file_hash(self.test_file)
        else:
            self.watcher._trigger_callbacks(self.test_file)
        
        # 第四次：用户修改
        content4 = "用户第二次修改"
        with open(self.test_file, "w") as f:
            f.write(content4)
        
        if self.watcher._is_programmatic_change(self.test_file):
            self.watcher._update_file_hash(self.test_file)
        else:
            self.watcher._trigger_callbacks(self.test_file)
        
        # 验证结果：应该只有2次用户修改触发了回调
        expected_callbacks = initial_callback_count + 2
        self.assertEqual(self.callback_count, expected_callbacks, 
                        f"应该触发 {expected_callbacks} 次回调（2次用户修改）")
    
    def test_hash_calculation(self):
        """测试哈希计算功能"""
        # 测试文件哈希计算
        content = "测试内容"
        with open(self.test_file, "w") as f:
            f.write(content)
        
        hash1 = self.watcher._calculate_file_hash(self.test_file)
        self.assertIsInstance(hash1, str)
        self.assertEqual(len(hash1), 32)  # MD5 哈希长度为32
        
        # 相同内容应该产生相同哈希
        hash2 = self.watcher._calculate_file_hash(self.test_file)
        self.assertEqual(hash1, hash2)
        
        # 不同内容应该产生不同哈希
        with open(self.test_file, "w") as f:
            f.write("不同的内容")
        
        hash3 = self.watcher._calculate_file_hash(self.test_file)
        self.assertNotEqual(hash1, hash3)
    
    def test_expected_hash_for_content(self):
        """测试内容预期哈希设置"""
        content = "预期内容"
        
        # 设置预期哈希
        self.watcher.set_expected_hash_for_content(self.test_file, content)
        
        # 写入相同内容
        with open(self.test_file, "w") as f:
            f.write(content)
        
        # 应该识别为程序修改
        self.assertTrue(self.watcher._is_programmatic_change(self.test_file))
        
        # 写入不同内容
        with open(self.test_file, "w") as f:
            f.write("不同内容")
        
        # 应该识别为用户修改
        self.assertFalse(self.watcher._is_programmatic_change(self.test_file))
    
    def test_file_initialization(self):
        """测试文件初始化"""
        # 创建新的临时文件
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            new_file = f.name
            f.write("初始化内容")
        
        try:
            # 添加文件监听（会触发初始化）
            callback_count = 0
            def callback(path):
                nonlocal callback_count
                callback_count += 1
            
            self.watcher.add_file(new_file, callback)
            
            # 验证文件哈希已被初始化
            self.assertIn(new_file, self.watcher._file_hashes)
            
            # 清理
            self.watcher.remove_file(new_file)
            self.assertNotIn(new_file, self.watcher._file_hashes)
            self.assertNotIn(new_file, self.watcher._expected_hashes)
            
        finally:
            if os.path.exists(new_file):
                os.unlink(new_file)


class TestFileWatcherIntegration(unittest.TestCase):
    """FileWatcher 集成测试"""
    
    def test_complete_workflow(self):
        """测试完整的工作流程"""
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            test_file = f.name
            f.write("初始内容")
        
        try:
            watcher = FileWatcher()
            callback_count = 0
            
            def callback(path):
                nonlocal callback_count
                callback_count += 1
            
            # 添加监听
            watcher.add_file(test_file, callback)
            
            # 模拟完整的程序修改流程
            program_content = "程序修改内容"
            watcher.set_expected_hash_for_content(test_file, program_content)
            
            with open(test_file, "w") as f:
                f.write(program_content)
            
            # 模拟文件监听事件处理
            if watcher._is_programmatic_change(test_file):
                watcher._update_file_hash(test_file)
            else:
                watcher._trigger_callbacks(test_file)
            
            # 验证程序修改没有触发回调
            self.assertEqual(callback_count, 0)
            
            # 模拟用户修改
            user_content = "用户修改内容"
            with open(test_file, "w") as f:
                f.write(user_content)
            
            # 模拟文件监听事件处理
            if watcher._is_programmatic_change(test_file):
                watcher._update_file_hash(test_file)
            else:
                watcher._trigger_callbacks(test_file)
            
            # 验证用户修改触发了回调
            self.assertEqual(callback_count, 1)
            
            # 清理
            watcher.remove_file(test_file)
            
        finally:
            if os.path.exists(test_file):
                os.unlink(test_file)


if __name__ == "__main__":
    unittest.main(verbosity=2)