#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Token计算器测试用例"""

import unittest
from unittest.mock import Mock, patch

from echo.agents.core.token_calculator import TokenCalculator
from echo.llms.schema import Message


class TestTokenCalculator(unittest.TestCase):
    """Token计算器测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.calculator = TokenCalculator()
    
    def test_calculate_tokens_string(self):
        """测试计算字符串的token数"""
        text = "Hello, world!"
        token_count = self.calculator.calculate_tokens(text)
        
        # 验证返回值是正整数
        self.assertIsInstance(token_count, int)
        self.assertGreater(token_count, 0)
    
    def test_calculate_tokens_empty_string(self):
        """测试计算空字符串的token数"""
        token_count = self.calculator.calculate_tokens("")
        self.assertEqual(token_count, 0)
    
    def test_calculate_tokens_chinese_text(self):
        """测试计算中文文本的token数"""
        chinese_text = "你好，世界！这是一个测试。"
        token_count = self.calculator.calculate_tokens(chinese_text)
        
        self.assertIsInstance(token_count, int)
        self.assertGreater(token_count, 0)
    
    def test_calculate_tokens_long_text(self):
        """测试计算长文本的token数"""
        long_text = "This is a very long text. " * 100
        token_count = self.calculator.calculate_tokens(long_text)
        
        # 长文本应该有更多token
        short_text = "This is a short text."
        short_token_count = self.calculator.calculate_tokens(short_text)
        
        self.assertGreater(token_count, short_token_count)
    
    def test_calculate_tokens_message(self):
        """测试计算单个消息的token数"""
        message = Message(role="user", content="Hello, how are you?")
        token_count = self.calculator.calculate_tokens(message)
        
        self.assertIsInstance(token_count, int)
        self.assertGreater(token_count, 0)
    
    def test_calculate_tokens_message_list(self):
        """测试计算消息列表的token数"""
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there!"),
            Message(role="user", content="How are you?")
        ]
        
        total_tokens = self.calculator.calculate_tokens(messages)
        
        # 验证总token数大于单个消息的token数
        single_message_tokens = self.calculator.calculate_tokens(messages[0])
        self.assertGreater(total_tokens, single_message_tokens)
    
    def test_calculate_tokens_empty_message_list(self):
        """测试计算空消息列表的token数"""
        token_count = self.calculator.calculate_tokens([])
        self.assertEqual(token_count, 0)
    
    def test_calculate_tokens_message_with_system_role(self):
        """测试计算系统角色消息的token数"""
        system_message = Message(role="system", content="You are a helpful assistant.")
        token_count = self.calculator.calculate_tokens(system_message)
        
        self.assertIsInstance(token_count, int)
        self.assertGreater(token_count, 0)
    
    def test_calculate_tokens_message_with_metadata(self):
        """测试计算带元数据消息的token数"""
        message = Message(
            role="user",
            content="Hello",
            metadata={"timestamp": "2024-01-01T00:00:00Z"}
        )
        
        token_count = self.calculator.calculate_tokens(message)
        
        # 元数据不应该影响token计算（只计算content）
        simple_message = Message(role="user", content="Hello")
        simple_token_count = self.calculator.calculate_tokens(simple_message)
        
        self.assertEqual(token_count, simple_token_count)
    
    def test_calculate_tokens_different_models(self):
        """测试不同模型的token计算"""
        text = "This is a test message for token calculation."
        
        # 测试GPT-3.5模型
        gpt35_calculator = TokenCalculator(model_name="gpt-3.5-turbo")
        gpt35_tokens = gpt35_calculator.calculate_tokens(text)
        
        # 测试GPT-4模型
        gpt4_calculator = TokenCalculator(model_name="gpt-4")
        gpt4_tokens = gpt4_calculator.calculate_tokens(text)
        
        # 两个模型的token计算可能不同，但都应该是正整数
        self.assertIsInstance(gpt35_tokens, int)
        self.assertIsInstance(gpt4_tokens, int)
        self.assertGreater(gpt35_tokens, 0)
        self.assertGreater(gpt4_tokens, 0)
    
    def test_calculate_tokens_unsupported_model(self):
        """测试不支持的模型"""
        with self.assertRaises(ValueError) as context:
            TokenCalculator(model_name="unsupported-model")
        
        self.assertIn("不支持的模型", str(context.exception))
    
    def test_calculate_tokens_special_characters(self):
        """测试包含特殊字符的文本"""
        special_text = "Hello! @#$%^&*()_+-=[]{}|;':,.<>?/~`"
        token_count = self.calculator.calculate_tokens(special_text)
        
        self.assertIsInstance(token_count, int)
        self.assertGreater(token_count, 0)
    
    def test_calculate_tokens_code_content(self):
        """测试代码内容的token计算"""
        code_content = '''
def hello_world():
    print("Hello, World!")
    return "success"

if __name__ == "__main__":
    hello_world()
'''
        
        token_count = self.calculator.calculate_tokens(code_content)
        
        self.assertIsInstance(token_count, int)
        self.assertGreater(token_count, 0)
    
    def test_calculate_tokens_markdown_content(self):
        """测试Markdown内容的token计算"""
        markdown_content = '''
# 标题

这是一个**粗体**文本和*斜体*文本。

## 代码块

```python
print("Hello, World!")
```

- 列表项1
- 列表项2
- 列表项3

[链接](https://example.com)
'''
        
        token_count = self.calculator.calculate_tokens(markdown_content)
        
        self.assertIsInstance(token_count, int)
        self.assertGreater(token_count, 0)
    
    def test_calculate_tokens_json_content(self):
        """测试JSON内容的token计算"""
        json_content = '''
{
    "name": "John Doe",
    "age": 30,
    "city": "New York",
    "hobbies": ["reading", "swimming", "coding"],
    "address": {
        "street": "123 Main St",
        "zipcode": "10001"
    }
}
'''
        
        token_count = self.calculator.calculate_tokens(json_content)
        
        self.assertIsInstance(token_count, int)
        self.assertGreater(token_count, 0)
    
    def test_calculate_tokens_mixed_languages(self):
        """测试混合语言内容的token计算"""
        mixed_content = "Hello 你好 Bonjour こんにちは 안녕하세요 Привет"
        token_count = self.calculator.calculate_tokens(mixed_content)
        
        self.assertIsInstance(token_count, int)
        self.assertGreater(token_count, 0)
    
    def test_calculate_tokens_very_long_text(self):
        """测试非常长文本的token计算"""
        # 创建一个很长的文本（约10000字符）
        very_long_text = "This is a test sentence. " * 400
        token_count = self.calculator.calculate_tokens(very_long_text)
        
        self.assertIsInstance(token_count, int)
        self.assertGreater(token_count, 1000)  # 应该有很多token
    
    def test_calculate_tokens_whitespace_handling(self):
        """测试空白字符处理"""
        text_with_spaces = "Hello    world    with    many    spaces"
        text_normal = "Hello world with many spaces"
        
        tokens_with_spaces = self.calculator.calculate_tokens(text_with_spaces)
        tokens_normal = self.calculator.calculate_tokens(text_normal)
        
        # 多余的空格可能会影响token计算
        self.assertIsInstance(tokens_with_spaces, int)
        self.assertIsInstance(tokens_normal, int)
        self.assertGreater(tokens_with_spaces, 0)
        self.assertGreater(tokens_normal, 0)
    
    def test_calculate_tokens_newlines_and_tabs(self):
        """测试换行符和制表符处理"""
        text_with_formatting = "Line 1\n\tIndented line\n\n\tAnother indented line"
        token_count = self.calculator.calculate_tokens(text_with_formatting)
        
        self.assertIsInstance(token_count, int)
        self.assertGreater(token_count, 0)
    
    @patch('echo.agents.core.token_calculator.logger')
    def test_calculate_tokens_with_logging(self, mock_logger):
        """测试token计算时的日志记录"""
        text = "Test message for logging"
        
        # 启用详细日志
        calculator = TokenCalculator(model_name="gpt-3.5-turbo")
        token_count = calculator.calculate_tokens(text)
        
        self.assertIsInstance(token_count, int)
        self.assertGreater(token_count, 0)
    
    def test_calculate_tokens_consistency(self):
        """测试token计算的一致性"""
        text = "This is a consistency test message."
        
        # 多次计算同一文本应该得到相同结果
        count1 = self.calculator.calculate_tokens(text)
        count2 = self.calculator.calculate_tokens(text)
        count3 = self.calculator.calculate_tokens(text)
        
        self.assertEqual(count1, count2)
        self.assertEqual(count2, count3)
    
    def test_calculate_tokens_message_role_impact(self):
        """测试消息角色对token计算的影响"""
        content = "This is a test message."
        
        user_message = Message(role="user", content=content)
        assistant_message = Message(role="assistant", content=content)
        system_message = Message(role="system", content=content)
        
        user_tokens = self.calculator.calculate_tokens(user_message)
        assistant_tokens = self.calculator.calculate_tokens(assistant_message)
        system_tokens = self.calculator.calculate_tokens(system_message)
        
        # 不同角色可能有不同的token开销
        self.assertIsInstance(user_tokens, int)
        self.assertIsInstance(assistant_tokens, int)
        self.assertIsInstance(system_tokens, int)
        
        # 但都应该大于0
        self.assertGreater(user_tokens, 0)
        self.assertGreater(assistant_tokens, 0)
        self.assertGreater(system_tokens, 0)
    
    def test_calculate_tokens_invalid_input_type(self):
        """测试无效输入类型"""
        with self.assertRaises(TypeError) as context:
            self.calculator.calculate_tokens(123)  # 数字类型
        
        self.assertIn("不支持的输入类型", str(context.exception))
        
        with self.assertRaises(TypeError) as context:
            self.calculator.calculate_tokens({"key": "value"})  # 字典类型
        
        self.assertIn("不支持的输入类型", str(context.exception))


if __name__ == '__main__':
    unittest.main()