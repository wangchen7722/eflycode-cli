#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import tempfile
from echo.tool.file.file_tool import SearchFilesTool


def test_search_files_tool():
    """测试SearchFilesTool的功能"""

    # 创建临时测试文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        test_content = """# 这是一个测试文件
import os
import sys

def hello_world():
    print("Hello, World!")
    return "success"

class TestClass:
    def __init__(self):
        self.name = "test"
    
    def get_name(self):
        return self.name

if __name__ == "__main__":
    hello_world()
    test = TestClass()
    print(test.get_name())
"""
        f.write(test_content)
        test_file_path = f.name

    try:
        # 创建SearchFilesTool实例
        tool = SearchFilesTool()

        print("=== SearchFilesTool 属性测试 ===")
        print(f"工具名称: {tool.name}")
        print(f"工具类型: {tool.type}")
        print(f"需要审批: {tool.should_approval}")
        print(f"工具描述: {tool.description[:100]}...")  # 只显示前100个字符
        print(f"参数定义: {tool.parameters}")
        print(f"示例数量: {len(tool.examples)}")
        print()

        print("=== 测试1: 搜索函数定义 ===")
        result1 = tool.run(
            path=os.path.dirname(test_file_path),
            regex=r'def \w+\(',
            pattern='*.py'
        )
        print(result1)
        print()

        print("=== 测试2: 搜索类定义 ===")
        result2 = tool.run(
            path=os.path.dirname(test_file_path),
            regex=r'class \w+:',
            pattern='*.py'
        )
        print(result2)
        print()

        print("=== 测试3: 搜索import语句 ===")
        result3 = tool.run(
            path=os.path.dirname(test_file_path),
            regex=r'import \w+',
            pattern='*.py'
        )
        print(result3)
        print()

        print("=== 测试4: 搜索字符串 ===")
        result4 = tool.run(
            path=os.path.dirname(test_file_path),
            regex=r'Hello, World!',
            pattern='*.py'
        )
        print(result4)
        print()

        print("=== 测试5: 搜索不存在的内容 ===")
        result5 = tool.run(
            path=os.path.dirname(test_file_path),
            regex=r'nonexistent_pattern',
            pattern='*.py'
        )
        print(result5)
        print()

        print("=== 测试6: 无效正则表达式 ===")
        try:
            result6 = tool.run(
                path=os.path.dirname(test_file_path),
                regex=r'[invalid',
                pattern='*.py'
            )
            print(result6)
        except Exception as e:
            print(f"捕获到预期的异常: {e}")
        print()

        print("=== 测试7: 不存在的路径 ===")
        try:
            result7 = tool.run(
                path='/nonexistent/path',
                regex=r'test',
                pattern='*.py'
            )
            print(result7)
        except Exception as e:
            print(f"捕获到预期的异常: {e}")
        print()

    finally:
        # 清理临时文件
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)


if __name__ == "__main__":
    test_search_files_tool()
