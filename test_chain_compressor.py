#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试压缩器链功能的简单脚本
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'echo'))

from echo.llms.schema import Message
from echo.config import CompressionConfig, CompressionStrategy
from echo.agents.core.context_compressor import ContextCompressor

def test_chain_compressor():
    """测试压缩器链功能"""
    print("=== 测试压缩器链功能 ===")
    
    # 创建测试消息
    messages = [
        Message(role="system", content="你是一个有用的AI助手。"),
        Message(role="user", content="你好，请介绍一下Python编程语言。"),
        Message(role="assistant", content="Python是一种高级编程语言，由Guido van Rossum在1989年发明。它以简洁、易读的语法而闻名，广泛应用于Web开发、数据科学、人工智能等领域。Python支持多种编程范式，包括面向对象、函数式和过程式编程。"),
        Message(role="user", content="Python有哪些主要特点？"),
        Message(role="assistant", content="Python的主要特点包括：1. 语法简洁明了，易于学习和使用；2. 跨平台兼容性好；3. 拥有丰富的标准库和第三方库；4. 支持多种编程范式；5. 解释型语言，开发效率高；6. 开源免费；7. 社区活跃，文档完善。"),
        Message(role="user", content="能给我一个Python的Hello World示例吗？"),
        Message(role="assistant", content="当然可以！这是一个简单的Python Hello World示例：\n\n```python\nprint('Hello, World!')\n```\n\n这就是Python中最简单的程序，只需要一行代码就能输出'Hello, World!'到控制台。"),
    ]
    
    print(f"原始消息数量: {len(messages)}")
    
    # 测试CHAIN策略
    print("\n--- 测试CHAIN策略 ---")
    chain_config = CompressionConfig(
        strategy=CompressionStrategy.CHAIN,
        max_tokens=200,
        chain_compressor_types=["key_extraction", "sliding_window"],
        chain_selection_strategy="best_ratio"
    )
    
    chain_compressor = ContextCompressor(chain_config)
    chain_result = chain_compressor.compress_messages(messages)
    
    print(f"压缩后消息数量: {len(chain_result.compressed_messages)}")
    print(f"原始token数: {chain_result.original_token_count}")
    print(f"压缩后token数: {chain_result.compressed_token_count}")
    print(f"压缩比率: {chain_result.compression_ratio:.2%}")
    print(f"压缩策略: {chain_result.metadata.get('strategy', 'unknown')}")
    print(f"实现方式: {chain_result.metadata.get('implementation', 'unknown')}")
    
    # 测试HYBRID策略（重构后的）
    print("\n--- 测试重构后的HYBRID策略 ---")
    hybrid_config = CompressionConfig(
        strategy=CompressionStrategy.HYBRID,
        max_tokens=200
    )
    
    hybrid_compressor = ContextCompressor(hybrid_config)
    hybrid_result = hybrid_compressor.compress_messages(messages)
    
    print(f"压缩后消息数量: {len(hybrid_result.compressed_messages)}")
    print(f"原始token数: {hybrid_result.original_token_count}")
    print(f"压缩后token数: {hybrid_result.compressed_token_count}")
    print(f"压缩比率: {hybrid_result.compression_ratio:.2%}")
    print(f"压缩策略: {hybrid_result.metadata.get('strategy', 'unknown')}")
    print(f"实现方式: {hybrid_result.metadata.get('implementation', 'unknown')}")
    
    # 比较两种策略的结果
    print("\n--- 结果比较 ---")
    print(f"CHAIN策略压缩比率: {chain_result.compression_ratio:.2%}")
    print(f"HYBRID策略压缩比率: {hybrid_result.compression_ratio:.2%}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_chain_compressor()