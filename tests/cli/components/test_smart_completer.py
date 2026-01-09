"""SmartCompleter 测试"""

import unittest
from unittest.mock import Mock, MagicMock, patch

from prompt_toolkit.document import Document

from eflycode.cli.components.smart_completer import SmartCompleter


class TestSmartCompleter(unittest.TestCase):
    """SmartCompleter 测试类"""

    def setUp(self):
        """设置测试环境"""
        self.completer = SmartCompleter()

    def test_register_command(self):
        """测试命令注册"""
        # 测试注册新命令
        handler = Mock(return_value=True)
        self.completer.register_command(
            command="/test",
            description="测试命令",
            handler=handler,
        )
        
        # 验证命令已注册
        self.assertIn("/test", self.completer._commands)
        self.assertEqual(self.completer._commands["/test"]["description"], "测试命令")
        self.assertEqual(self.completer._commands["/test"]["handler"], handler)

    def test_register_command_invalid(self):
        """测试注册无效命令"""
        # 测试不以 / 开头的命令
        with self.assertRaises(ValueError):
            self.completer.register_command(
                command="test",
                description="测试命令",
            )

    def test_get_completions_empty(self):
        """测试空输入时的补全"""
        document = Document("")
        completions = list(self.completer.get_completions(document, None))
        
        # 空输入时不提供补全，需要先输入 /
        self.assertEqual(len(completions), 0)

    def test_get_completions_partial(self):
        """测试部分输入时的补全"""
        document = Document("/mo")
        completions = list(self.completer.get_completions(document, None))
        
        # 应该返回匹配的命令
        self.assertGreater(len(completions), 0)
        # 检查是否包含 /model 的补全
        # display 可能是 FormattedText，需要转换为字符串比较
        model_completion = None
        for c in completions:
            display_str = str(c.display) if hasattr(c.display, '__str__') else c.display
            if "/model" in display_str:
                model_completion = c
                break
        self.assertIsNotNone(model_completion)
        # 检查补全文本是完整命令
        self.assertEqual(model_completion.text, "/model")
        self.assertEqual(model_completion.start_position, -3)

    def test_get_completions_file_token(self):
        """测试 # 文件补全"""
        with patch("eflycode.cli.components.smart_completer.get_file_manager") as get_file_manager:
            file_manager = MagicMock()
            file_manager.fuzzy_find.return_value = ["src/main.py", "README.md"]
            get_file_manager.return_value = file_manager

            document = Document("check #sm")
            completions = list(self.completer.get_completions(document, None))
            self.assertEqual(len(completions), 2)
            self.assertEqual(completions[0].text, "#src/main.py")

    def test_get_completions_full_command(self):
        """测试完整命令输入时的补全"""
        document = Document("/model")
        completions = list(self.completer.get_completions(document, None))
        
        # 完整命令不应该有补全
        self.assertEqual(len(completions), 0)

    def test_handle_command(self):
        """测试命令处理"""
        # 注册测试命令
        handler = Mock(return_value=True)
        self.completer.register_command(
            command="/test",
            description="测试命令",
            handler=handler,
        )
        
        # 处理命令
        result = self.completer.handle_command("/test")
        
        # 验证处理函数被调用
        handler.assert_called_once_with("/test")
        self.assertTrue(result)

    def test_handle_command_not_found(self):
        """测试处理不存在的命令"""
        result = self.completer.handle_command("/nonexistent")
        self.assertFalse(result)

    def test_set_command_handler(self):
        """测试设置命令处理函数"""
        # 设置 /model 的处理函数
        handler = Mock(return_value=True)
        self.completer.set_command_handler("/model", handler)
        
        # 验证处理函数已设置
        self.assertEqual(self.completer._commands["/model"]["handler"], handler)
        
        # 处理命令
        result = self.completer.handle_command("/model")
        handler.assert_called_once_with("/model")
        self.assertTrue(result)

    def test_set_command_handler_not_registered(self):
        """测试设置未注册命令的处理函数"""
        handler = Mock(return_value=True)
        with self.assertRaises(ValueError):
            self.completer.set_command_handler("/nonexistent", handler)

    def test_get_command_handler(self):
        """测试获取命令处理函数"""
        # 设置处理函数
        handler = Mock(return_value=True)
        self.completer.set_command_handler("/model", handler)
        
        # 获取处理函数
        retrieved_handler = self.completer.get_command_handler("/model")
        self.assertEqual(retrieved_handler, handler)
        
        # 获取不存在的命令
        retrieved_handler = self.completer.get_command_handler("/nonexistent")
        self.assertIsNone(retrieved_handler)


if __name__ == "__main__":
    unittest.main()

