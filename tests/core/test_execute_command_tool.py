import json
import os
import tempfile
import unittest

from eflycode.core.tool.errors import ToolExecutionError
from eflycode.core.tool.execute_command_tool import ExecuteCommandTool


class TestExecuteCommandTool(unittest.TestCase):
    """ExecuteCommandTool 测试类"""

    def setUp(self):
        """设置测试环境"""
        self.tool = ExecuteCommandTool()
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, "test.txt")
        
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("test content\n")

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_tool_properties(self):
        """测试工具基本属性"""
        self.assertEqual(self.tool.name, "execute_command")
        self.assertEqual(self.tool.type, "function")
        self.assertEqual(self.tool.permission, "read")
        self.assertIsNotNone(self.tool.description)
        self.assertIsNotNone(self.tool.parameters)

    def test_whitelist_allowed_commands(self):
        """测试白名单中允许的命令"""
        # 为每个命令定义合适的测试参数
        command_tests = {
            "ls": "ls",
            "cat": f"cat {self.test_file}",  # cat 需要文件参数，否则会等待输入
            "grep": f"grep test {self.test_file}",
            "pwd": "pwd",
            "echo": "echo test",
            "git": "git --version",
            "python": "python --version",
            "pip": "pip --version",
        }
        
        for cmd, test_command in command_tests.items():
            with self.subTest(command=cmd):
                try:
                    result = self.tool.run(command=test_command)
                    output = json.loads(result)
                    self.assertIn("stdout", output)
                    self.assertIn("stderr", output)
                    self.assertIn("exit_code", output)
                    self.assertIn("success", output)
                except ToolExecutionError as e:
                    # 某些命令可能不存在或执行失败，这是可以接受的
                    # 只要不是"不在允许列表中"的错误即可
                    error_msg = str(e)
                    self.assertNotIn("不在允许列表中", error_msg, 
                                   f"命令 {cmd} 应该被允许，但被拒绝了")

    def test_whitelist_rejected_commands(self):
        """测试白名单中拒绝的命令"""
        rejected_commands = ["rm", "rmdir", "del", "format", "shutdown", "reboot"]
        
        for cmd in rejected_commands:
            with self.subTest(command=cmd):
                with self.assertRaises(ToolExecutionError) as context:
                    self.tool.run(command=f"{cmd} /test")
                self.assertIn("不在允许列表中", str(context.exception))

    def test_execute_simple_command(self):
        """测试执行简单命令"""
        result = self.tool.run(command="echo hello")
        output = json.loads(result)
        
        self.assertEqual(output["exit_code"], 0)
        self.assertTrue(output["success"])
        self.assertIn("hello", output["stdout"])

    def test_execute_command_with_output(self):
        """测试执行有输出的命令"""
        result = self.tool.run(command=f"cat {self.test_file}")
        output = json.loads(result)
        
        self.assertEqual(output["exit_code"], 0)
        self.assertTrue(output["success"])
        self.assertIn("test content", output["stdout"])

    def test_execute_command_with_error(self):
        """测试执行失败的命令"""
        result = self.tool.run(command="ls /nonexistent_directory_12345")
        output = json.loads(result)
        
        self.assertNotEqual(output["exit_code"], 0)
        self.assertFalse(output["success"])
        self.assertIsNotNone(output["stderr"])

    def test_execute_command_with_workdir(self):
        """测试指定工作目录"""
        result = self.tool.run(command="pwd", workdir=self.test_dir)
        output = json.loads(result)
        
        self.assertEqual(output["exit_code"], 0)
        self.assertTrue(output["success"])
        # 工作目录应该包含测试目录的路径
        self.assertIn(self.test_dir, output["stdout"])

    def test_execute_command_default_workdir(self):
        """测试默认工作目录"""
        result = self.tool.run(command="pwd")
        output = json.loads(result)
        
        self.assertEqual(output["exit_code"], 0)
        self.assertTrue(output["success"])
        # 应该返回某个有效路径
        self.assertIsNotNone(output["stdout"])

    def test_execute_command_with_timeout(self):
        """测试命令超时"""
        # 使用 python3 命令执行一个会超时的脚本
        # 注意：在某些系统上 python 可能不存在，使用 python3
        import sys
        python_cmd = "python3" if sys.platform != "win32" else "python"
        
        with self.assertRaises(ToolExecutionError) as context:
            self.tool.run(command=f'{python_cmd} -c "import time; time.sleep(2)"', timeout=1)
        error_msg = str(context.exception)
        # 超时异常可能包含"超时"或"TimeoutExpired"
        self.assertTrue("超时" in error_msg or "timeout" in error_msg.lower() or "TimeoutExpired" in error_msg)

    def test_execute_command_empty_command(self):
        """测试空命令"""
        with self.assertRaises(ToolExecutionError) as context:
            self.tool.run(command="")
        self.assertIn("不能为空", str(context.exception))

    def test_execute_command_whitespace_only(self):
        """测试只有空格的命令"""
        with self.assertRaises(ToolExecutionError) as context:
            self.tool.run(command="   ")
        self.assertIn("不能为空", str(context.exception))

    def test_execute_command_nonexistent_workdir(self):
        """测试不存在的工作目录"""
        with self.assertRaises(ToolExecutionError) as context:
            self.tool.run(command="ls", workdir="/nonexistent/directory/12345")
        self.assertIn("工作目录不存在", str(context.exception))

    def test_execute_command_file_as_workdir(self):
        """测试使用文件作为工作目录"""
        with self.assertRaises(ToolExecutionError) as context:
            self.tool.run(command="ls", workdir=self.test_file)
        self.assertIn("不是目录", str(context.exception))

    def test_execute_command_output_format(self):
        """测试输出格式"""
        result = self.tool.run(command="echo test")
        output = json.loads(result)
        
        # 验证输出格式
        self.assertIsInstance(output, dict)
        self.assertIn("stdout", output)
        self.assertIn("stderr", output)
        self.assertIn("exit_code", output)
        self.assertIn("success", output)
        
        # 验证类型
        self.assertIsInstance(output["stdout"], str)
        self.assertIsInstance(output["stderr"], str)
        self.assertIsInstance(output["exit_code"], int)
        self.assertIsInstance(output["success"], bool)

    def test_execute_command_success_flag(self):
        """测试 success 标志"""
        # 成功命令
        result = self.tool.run(command="echo success")
        output = json.loads(result)
        self.assertTrue(output["success"])
        self.assertEqual(output["exit_code"], 0)
        
        # 失败命令
        result = self.tool.run(command="ls /nonexistent_12345")
        output = json.loads(result)
        self.assertFalse(output["success"])
        self.assertNotEqual(output["exit_code"], 0)

    def test_execute_command_with_arguments(self):
        """测试带参数的命令"""
        result = self.tool.run(command=f"grep test {self.test_file}")
        output = json.loads(result)
        
        self.assertEqual(output["exit_code"], 0)
        self.assertTrue(output["success"])
        self.assertIn("test content", output["stdout"])

    def test_execute_command_with_quotes(self):
        """测试带引号的命令"""
        result = self.tool.run(command='echo "hello world"')
        output = json.loads(result)
        
        self.assertEqual(output["exit_code"], 0)
        self.assertTrue(output["success"])
        self.assertIn("hello world", output["stdout"])

    def test_execute_command_timeout_range(self):
        """测试超时时间范围"""
        # 测试最小超时时间
        result = self.tool.run(command="echo test", timeout=1)
        output = json.loads(result)
        self.assertTrue(output["success"])
        
        # 测试较大的超时时间
        result = self.tool.run(command="echo test", timeout=300)
        output = json.loads(result)
        self.assertTrue(output["success"])

