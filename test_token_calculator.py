#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Token计算器测试脚本

演示三种token计算策略的使用方法：
1. 估算策略（ESTIMATE）
2. API策略（API）
3. Transformers策略（TRANSFORMERS）
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from echo.config import TokenCalculationStrategy, CompressionConfig
from echo.agents.core.token_calculator import create_token_calculator
from echo.llms.schema import Message


def test_estimate_strategy():
    """测试估算策略"""
    print("\n=== 测试估算策略 ===")
    calculator = create_token_calculator(TokenCalculationStrategy.ESTIMATE)
    
    test_texts = [
        "Hello, world!",
        "你好，世界！",
        "This is a longer text with multiple sentences. It contains both English and Chinese characters: 这是一个包含中英文的测试文本。",
        ""  # 空文本
    ]
    
    for text in test_texts:
        tokens = calculator.calculate_tokens(text)
        print(f"文本: '{text}' -> Token数: {tokens}")


def test_transformers_strategy():
    """测试Transformers策略"""
    print("\n=== 测试Transformers策略 ===")
    
    try:
        calculator = create_token_calculator(
            TokenCalculationStrategy.TOKENIZER,
            model_name="gpt2"
        )
        
        test_texts = [
            "Hello, world!",
            "这是一个中文测试文本。",
            "Mixed language text: 中英文混合测试。"
        ]
        
        for text in test_texts:
            tokens = calculator.calculate_tokens(text)
            print(f"文本: '{text}' -> Token数: {tokens}")
            
    except ImportError as e:
        print(f"正确：捕获到预期的异常 - {e}")
        print("需要安装transformers库: pip install transformers")
    except Exception as e:
        print(f"Transformers策略测试失败: {e}")


def test_api_strategy():
    """测试API策略（参数校验）"""
    print("\n=== 测试API策略 ===")
    
    # 测试缺少API配置时抛出异常
    try:
        config = CompressionConfig(
            token_calculation_strategy=TokenCalculationStrategy.API,
            api_base_url="",  # 空的API URL
            api_key="",      # 空的API Key
            model_name="gpt-3.5-turbo"
        )
        
        calculator = create_token_calculator(
            strategy=config.token_calculation_strategy,
            api_base_url=config.api_base_url,
            api_key=config.api_key,
            model_name=config.model_name
        )
        print("错误：应该抛出异常但没有抛出")
    except ValueError as e:
        print(f"正确：捕获到预期的异常 - {e}")
    except Exception as e:
        print(f"错误：捕获到意外的异常 - {e}")


def test_messages_token_calculation():
    """测试消息列表的token计算"""
    print("\n=== 测试消息列表Token计算 ===")
    calculator = create_token_calculator(TokenCalculationStrategy.ESTIMATE)
    
    messages = [
        {"role": "user", "content": "你好，请介绍一下你自己。"},
        {"role": "assistant", "content": "你好！我是一个AI助手，可以帮助你解答问题和完成各种任务。"},
        {"role": "user", "content": "能帮我写一段Python代码吗？"}
    ]
    
    total_tokens = calculator.calculate_messages_tokens(messages)
    print(f"消息列表总Token数: {total_tokens}")
    
    for i, message in enumerate(messages):
        content = message.get('content', '')
        tokens = calculator.calculate_tokens(content)
        print(f"消息 {i+1} ({message['role']}): {tokens} tokens")


def test_compression_config_integration():
    """测试与CompressionConfig的集成"""
    print("\n=== 测试配置集成 ===")
    
    # 创建不同策略的配置
    configs = [
        CompressionConfig(token_calculation_strategy=TokenCalculationStrategy.ESTIMATE),
        CompressionConfig(
            token_calculation_strategy=TokenCalculationStrategy.TOKENIZER,
            model_name="gpt2"
        )
    ]
    
    test_text = "This is a test sentence for configuration integration."
    
    for i, config in enumerate(configs):
        try:
            calculator = create_token_calculator(
                strategy=config.token_calculation_strategy,
                model_name=config.model_name,
                tokenizer_cache_dir=config.tokenizer_cache_dir
            )
            tokens = calculator.calculate_tokens(test_text)
            print(f"配置 {i+1} ({config.token_calculation_strategy.value}): {tokens} tokens")
        except Exception as e:
            print(f"配置 {i+1} 测试失败: {e}")


def test_with_compression_config():
    """测试与CompressionConfig的集成"""
    print("\n=== 与CompressionConfig集成测试 ===")
    
    # 创建配置
    config = CompressionConfig(
        token_calculation_strategy=TokenCalculationStrategy.ESTIMATE,
        max_tokens=1000,
        compression_ratio=0.5
    )
    
    # 创建token计算器
    token_calculator = create_token_calculator(
        strategy=config.token_calculation_strategy,
        api_base_url=config.api_base_url,
        api_key=config.api_key,
        model_name=config.model_name,
        tokenizer_cache_dir=config.tokenizer_cache_dir
    )
    
    # 测试消息
    messages = [
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "assistant", "content": "I'm doing well, thank you for asking!"},
        {"role": "user", "content": "Can you help me with a coding problem?"},
        {"role": "assistant", "content": "Of course! I'd be happy to help you with your coding problem. What specific issue are you facing?"}
    ]
    
    # 直接测试token计算
    total_tokens = token_calculator.calculate_messages_tokens(messages)
    print(f"消息总token数: {total_tokens}")
    print(f"Token计算器类型: {type(token_calculator).__name__}")
    
    # 测试单个消息的token计算
    for i, message in enumerate(messages):
        content = message.get('content', '')
        tokens = token_calculator.calculate_tokens(content)
        print(f"消息{i+1}: {tokens} tokens - '{content[:50]}...'")


def main():
    """主函数"""
    print("Token计算器功能测试")
    print("=" * 50)
    
    # 测试各种策略
    test_estimate_strategy()
    test_transformers_strategy()
    test_api_strategy()
    test_messages_token_calculation()
    test_compression_config_integration()
    test_with_compression_config()
    
    print("\n=== 测试完成 ===")
    print("\n使用说明:")
    print("1. 估算策略: 无需额外依赖，基于字符数估算")
    print("2. API策略: 需要有效的API密钥和网络连接")
    print("3. Transformers策略: 需要安装transformers库")
    print("\n所有策略都会在失败时自动回退到估算策略")


if __name__ == "__main__":
    main()