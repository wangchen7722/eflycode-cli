import unittest
import platform
from echoai.cli.tools.command_tool import ExecuteCommandTool

class TestExecuteCommandTool(unittest.TestCase):
    def setUp(self):
        self.tool = ExecuteCommandTool()

    def test_command_timeout(self):
        """测试超时处理是否生效"""
        # 根据操作系统选择耗时命令
        if platform.system() == "Windows":
            command = "ping -n 31 127.0.0.1"
        else:
            command = "sleep 31"

        result = self.tool.run(command=command, timeout=30)
        self.assertIn("Error: Command execution timed out", result)

if __name__ == "__main__":
    unittest.main()
