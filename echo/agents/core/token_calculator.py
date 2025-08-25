#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Token计算器模块

提供多种token计算策略：
- 估算计算：基于字符数的简单估算
- API计算：通过API接口精确计算
- Transformers计算：使用HuggingFace tokenizer计算
"""

import json
import httpx
from abc import ABC, abstractmethod
from typing import List, Optional

try:
    from transformers import AutoTokenizer, PreTrainedTokenizer
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

from echo.llms.schema import Message
from echo.utils.logger import get_logger
from echo.config import TokenCalculationStrategy

logger = get_logger()


class TokenCalculator(ABC):
    """Token计算器基类"""
    
    @abstractmethod
    def calculate_tokens(self, text: str) -> int:
        """计算文本的token数量"""
        pass
    
    def calculate_messages_tokens(self, messages: List[Message]) -> int:
        """计算消息列表的总token数"""
        total_tokens = 0
        for message in messages:
            content = message.get("content", "")
            if isinstance(content, str):
                total_tokens += self.calculate_tokens(content)
        return total_tokens


class EstimateTokenCalculator(TokenCalculator):
    """基于估算的Token计算器"""
    
    def calculate_tokens(self, text: str) -> int:
        """估算文本token数量"""
        # 简单估算：1个token约等于4个英文字符或1.5个中文字符
        chinese_chars = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)


class TransformersTokenCalculator(TokenCalculator):
    """基于HuggingFace Transformers的Token计算器"""
    
    def __init__(self, model_name: str, cache_dir: Optional[str] = None):
        if not HAS_TRANSFORMERS:
            raise ImportError("TransformersTokenCalculator需要transformers库")
        
        self.model_name = model_name
        self.cache_dir = cache_dir
        self._tokenizer: "PreTrainedTokenizer" = None
        self._load_tokenizer()
    
    def _load_tokenizer(self):
        """延迟加载tokenizer"""
        from transformers import AutoTokenizer
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            cache_dir=self.cache_dir
        )
    
    def calculate_tokens(self, text: str) -> int:
        """使用transformers tokenizer计算token数量"""
        tokens = self._tokenizer.encode(text, add_special_tokens=True)
        return len(tokens)


def create_token_calculator(
    strategy: TokenCalculationStrategy = TokenCalculationStrategy.ESTIMATE,
    model_name: Optional[str] = None,
    tokenizer_cache_dir: Optional[str] = None
) -> TokenCalculator:
    """创建token计算器的工厂函数
    
    Args:
        strategy: token计算策略
        model_name: 模型名称（仅transformers策略需要）
        tokenizer_cache_dir: tokenizer缓存目录（仅transformers策略需要）
        
    Returns:
        TokenCalculator: token计算器实例
    """
    if strategy == TokenCalculationStrategy.ESTIMATE:
        return EstimateTokenCalculator()
    elif strategy == TokenCalculationStrategy.TOKENIZER:
        if not HAS_TRANSFORMERS:
            raise ImportError("transformers库不可用，请安装transformers库")
        if not model_name:
            raise ValueError("Transformers token计算需要指定model_name")
        return TransformersTokenCalculator(
            model_name=model_name,
            cache_dir=tokenizer_cache_dir
        )
    else:
        raise ValueError(f"未知的token计算策略: {strategy}")