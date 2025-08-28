#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上下文压缩器模块

提供智能的对话历史压缩功能，用于优化token使用和提升性能。
支持多种压缩策略：摘要压缩、关键信息提取、滑动窗口等。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


from echo.llms.schema import Message
from echo.llms.llm_engine import LLMEngine
from echo.utils.logger import get_logger
from echo.config import CompressionStrategy, CompressionConfig, TokenCalculationStrategy
from pydantic import BaseModel, Field
from echo.agents.core.context.compressor.sliding_window import SlidingWindowCompressor
from echo.agents.core.token_calculator import TokenCalculator, EstimateTokenCalculator, APITokenCalculator, HAS_TRANSFORMERS, TransformersTokenCalculator

logger = get_logger()


class CompressionResult(BaseModel):
    """压缩结果
    
    压缩器对消息列表进行压缩后的结果数据结构，包含:
    - 压缩后的消息列表
    - 原始消息数量
    - 压缩后消息数量
    - 压缩比率
    - 保留的token数量
    - 元数据信息
    """
    compressed_messages: List[Message] = Field(description="压缩后的消息列表")
    """压缩后得到的消息列表，包含所有经过压缩处理的消息"""

    original_count: int = Field(description="原始消息数量")
    """压缩前原始消息列表中的消息数量"""

    compressed_count: int = Field(description="压缩后的消息数量")
    """压缩后消息列表中的消息数量"""

    compression_ratio: float = Field(description="压缩比率，compressed_tokens / original_tokens")
    """压缩比率，用压缩后的token数除以原始token数得到的比值"""

    preserved_tokens: int = Field(description="保留的token数量")
    """压缩后保留下来的token总数"""

    metadata: Dict[str, Any] = Field(description="压缩相关的元数据信息，如压缩策略、原因等")
    """压缩过程的元数据信息，包括使用的压缩策略、压缩原因等附加信息"""

class BaseCompressor(ABC):
    """压缩器基类"""
    
    def __init__(self, config: CompressionConfig, token_calculator: TokenCalculator):
        self.config = config
        self.token_calculator = token_calculator
    
    @abstractmethod
    def compress(self, messages: List[Message]) -> CompressionResult:
        """压缩消息列表"""
        pass
    
    def _estimate_tokens(self, text: str) -> int:
        """估算文本token数量"""
        return self.token_calculator.calculate_tokens(text)
    
    def _calculate_messages_tokens(self, messages: List[Message]) -> int:
        """计算消息列表的总token数"""
        return self.token_calculator.calculate_messages_tokens(messages)


class SummaryCompressor(BaseCompressor):
    """基于摘要的压缩器"""
    
    def __init__(self, config: CompressionConfig, token_calculator: TokenCalculator, llm_engine):
        super().__init__(config, token_calculator)
        self.llm_engine = llm_engine
    
    def compress(self, messages: List[Message]) -> CompressionResult:
        """使用LLM生成摘要进行压缩"""
        if len(messages) < self.config.min_messages_to_compress:
            return CompressionResult(
                compressed_messages=messages,
                original_count=len(messages),
                compressed_count=len(messages),
                compression_ratio=1.0,
                preserved_tokens=self._calculate_messages_tokens(messages),
                metadata={"strategy": "no_compression", "reason": "insufficient_messages"}
            )
        
        # 保留最近的消息
        recent_messages = messages[-self.config.preserve_recent_messages:]
        messages_to_compress = messages[:-self.config.preserve_recent_messages]
        
        if not messages_to_compress:
            return CompressionResult(
                compressed_messages=messages,
                original_count=len(messages),
                compressed_count=len(messages),
                compression_ratio=1.0,
                preserved_tokens=self._calculate_messages_tokens(messages),
                metadata={"strategy": "no_compression", "reason": "all_recent"}
            )
        
        # 生成摘要
        summary = self._generate_summary(messages_to_compress)
        
        # 构建压缩后的消息列表
        compressed_messages = [
            {"role": "system", "content": f"对话历史摘要：{summary}"}
        ] + recent_messages
        
        original_tokens = self._calculate_messages_tokens(messages)
        compressed_tokens = self._calculate_messages_tokens(compressed_messages)
        
        return CompressionResult(
            compressed_messages=compressed_messages,
            original_count=len(messages),
            compressed_count=len(compressed_messages),
            compression_ratio=compressed_tokens / original_tokens if original_tokens > 0 else 1.0,
            preserved_tokens=compressed_tokens,
            metadata={
                "strategy": "summary",
                "summary_length": len(summary),
                "compressed_messages_count": len(messages_to_compress)
            }
        )
    
    def _generate_summary(self, messages: List[Message]) -> str:
        """生成对话摘要"""
        # 构建摘要提示
        conversation_text = "\n".join([
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
            for msg in messages
            if msg.get('content')
        ])
        
        summary_prompt = f"""
请对以下对话历史进行简洁的摘要，保留关键信息和上下文：

{conversation_text}

要求：
1. 摘要长度不超过{self.config.summary_max_tokens}个token
2. 保留重要的决策、结论和关键信息
3. 保持时间顺序和逻辑关系
4. 使用简洁明了的语言

摘要：
"""
        
        try:
            response = self.llm_engine.generate(
                messages=[{"role": "user", "content": summary_prompt}],
                stream=False,
                max_tokens=self.config.summary_max_tokens
            )
            return response["choices"][0]["message"].get("content", "摘要生成失败")
        except Exception as e:
            logger.error(f"摘要生成失败: {e}")
            return "对话历史摘要（生成失败，保留原始信息）"


class SlidingWindowCompressor(BaseCompressor):
    """滑动窗口压缩器"""
    
    def compress(self, messages: List[Message]) -> CompressionResult:
        """使用滑动窗口策略压缩"""
        if len(messages) <= self.config.preserve_recent_messages:
            return CompressionResult(
                compressed_messages=messages,
                original_count=len(messages),
                compressed_count=len(messages),
                compression_ratio=1.0,
                preserved_tokens=self._calculate_messages_tokens(messages),
                metadata={"strategy": "sliding_window", "reason": "within_window"}
            )
        
        # 保留最近的消息
        compressed_messages = messages[-self.config.preserve_recent_messages:]
        
        original_tokens = self._calculate_messages_tokens(messages)
        compressed_tokens = self._calculate_messages_tokens(compressed_messages)
        
        return CompressionResult(
            compressed_messages=compressed_messages,
            original_count=len(messages),
            compressed_count=len(compressed_messages),
            compression_ratio=compressed_tokens / original_tokens if original_tokens > 0 else 1.0,
            preserved_tokens=compressed_tokens,
            metadata={
                "strategy": "sliding_window",
                "window_size": self.config.preserve_recent_messages,
                "dropped_messages": len(messages) - len(compressed_messages)
            }
        )


class KeyExtractionCompressor(BaseCompressor):
    """关键信息提取压缩器"""
    
    def compress(self, messages: List[Message]) -> CompressionResult:
        """提取关键信息进行压缩"""
        if len(messages) < self.config.min_messages_to_compress:
            return CompressionResult(
                compressed_messages=messages,
                original_count=len(messages),
                compressed_count=len(messages),
                compression_ratio=1.0,
                preserved_tokens=self._calculate_messages_tokens(messages),
                metadata={"strategy": "key_extraction", "reason": "insufficient_messages"}
            )
        
        # 保留最近的消息
        recent_messages = messages[-self.config.preserve_recent_messages:]
        messages_to_process = messages[:-self.config.preserve_recent_messages]
        
        # 提取关键信息（简化版本）
        key_messages = self._extract_key_messages(messages_to_process)
        
        compressed_messages = key_messages + recent_messages
        
        original_tokens = self._calculate_messages_tokens(messages)
        compressed_tokens = self._calculate_messages_tokens(compressed_messages)
        
        return CompressionResult(
            compressed_messages=compressed_messages,
            original_count=len(messages),
            compressed_count=len(compressed_messages),
            compression_ratio=compressed_tokens / original_tokens if original_tokens > 0 else 1.0,
            preserved_tokens=compressed_tokens,
            metadata={
                "strategy": "key_extraction",
                "key_messages_count": len(key_messages),
                "processed_messages_count": len(messages_to_process)
            }
        )
    
    def _extract_key_messages(self, messages: List[Message]) -> List[Message]:
        """提取关键消息（简化实现）"""
        key_messages = []
        
        # 关键词列表
        key_indicators = [
            "重要", "关键", "决定", "结论", "总结", "问题", "错误", "成功", "失败",
            "important", "key", "critical", "decision", "conclusion", "summary",
            "problem", "error", "success", "failure", "issue", "solution"
        ]
        
        for message in messages:
            content = message.get('content', '')
            if isinstance(content, str):
                # 检查是否包含关键词
                if any(keyword in content.lower() for keyword in key_indicators):
                    key_messages.append(message)
                # 或者消息较长（可能包含重要信息）
                elif len(content) > 100:
                    key_messages.append(message)
        
        # 如果提取的关键消息太少，保留一些原始消息
        if len(key_messages) < len(messages) * 0.2:
            step = max(1, len(messages) // 5)
            key_messages.extend(messages[::step])
        
        return key_messages[:len(messages) // 2]  # 最多保留一半


class HybridCompressor(BaseCompressor):
    """混合压缩器"""
    
    def __init__(self, config: CompressionConfig, token_calculator: TokenCalculator, llm_engine: Optional[LLMEngine] = None):
        super().__init__(config, token_calculator)
        self.summary_compressor = SummaryCompressor(config, token_calculator, llm_engine) if llm_engine else None
        self.sliding_window_compressor = SlidingWindowCompressor(config, token_calculator)
        self.key_extraction_compressor = KeyExtractionCompressor(config, token_calculator)
    
    def compress(self, messages: List[Message]) -> CompressionResult:
        """使用混合策略压缩"""
        current_tokens = self._calculate_messages_tokens(messages)
        
        # 如果token数量在限制内，不压缩
        if current_tokens <= self.config.max_tokens:
            return CompressionResult(
                compressed_messages=messages,
                original_count=len(messages),
                compressed_count=len(messages),
                compression_ratio=1.0,
                preserved_tokens=current_tokens,
                metadata={"strategy": "hybrid", "reason": "within_limit"}
            )
        
        # 根据消息数量和token数量选择策略
        if len(messages) < self.config.min_messages_to_compress:
            # 消息数量少，使用滑动窗口
            return self.sliding_window_compressor.compress(messages)
        
        # 尝试关键信息提取
        key_result = self.key_extraction_compressor.compress(messages)
        
        # 如果关键信息提取效果不好，使用摘要压缩
        if (key_result.compression_ratio > 0.7 and 
            self.summary_compressor and 
            len(messages) >= self.config.min_messages_to_compress * 2):
            summary_result = self.summary_compressor.compress(messages)
            if summary_result.compression_ratio < key_result.compression_ratio:
                summary_result.metadata["fallback_from"] = "key_extraction"
                return summary_result
        
        return key_result


class ContextCompressor:
    """上下文压缩器主类"""
    
    def __init__(self, config: CompressionConfig, llm_engine: Optional[LLMEngine] = None):
        self.config = config
        self.llm_engine = llm_engine
        self._compressor = self._create_compressor()
    
    def _create_compressor(self) -> BaseCompressor:
        """创建压缩器实例"""
        # 创建token计算器
        token_calculator = create_token_calculator(
            strategy=self.config.token_calculation_strategy,
            api_base_url=self.config.api_base_url,
            api_key=self.config.api_key,
            model_name=self.config.model_name,
            tokenizer_cache_dir=self.config.tokenizer_cache_dir
        )
        
        if self.config.strategy == CompressionStrategy.SUMMARY:
            if not self.llm_engine:
                logger.warning("摘要压缩需要LLM引擎，回退到滑动窗口策略")
                return SlidingWindowCompressor(self.config, token_calculator)
            return SummaryCompressor(self.config, token_calculator, self.llm_engine)
        elif self.config.strategy == CompressionStrategy.SLIDING_WINDOW:
            return SlidingWindowCompressor(self.config, token_calculator)
        elif self.config.strategy == CompressionStrategy.KEY_EXTRACTION:
            return KeyExtractionCompressor(self.config, token_calculator)
        elif self.config.strategy == CompressionStrategy.CHAIN:
            from echo.agents.core.context.compressor.chain import CompressorChain, CompressorChainConfig, CompressorType
            
            # 将配置中的字符串转换为CompressorType枚举
            compressor_types = []
            for type_str in self.config.chain_compressor_types:
                try:
                    compressor_type = CompressorType(type_str)
                    compressor_types.append(compressor_type)
                except ValueError:
                    logger.warning(f"未知的压缩器类型: {type_str}")
            
            if not compressor_types:
                logger.warning("没有有效的压缩器类型，使用默认配置")
                compressor_types = [CompressorType.KEY_EXTRACTION, CompressorType.SLIDING_WINDOW]
            
            chain_config = CompressorChainConfig(
                compressor_types=compressor_types,
                selection_strategy=self.config.chain_selection_strategy
            )
            
            return CompressorChain(self.config, token_calculator, chain_config, self.llm_engine)
        else:  # HYBRID
            return HybridCompressor(self.config, token_calculator, self.llm_engine)
    
    def compress_messages(self, messages: List[Message]) -> CompressionResult:
        """压缩消息列表
        
        Args:
            messages: 要压缩的消息列表
            
        Returns:
            CompressionResult: 压缩结果
        """
        try:
            result = self._compressor.compress(messages)
            logger.info(
                f"上下文压缩完成: {result.original_count} -> {result.compressed_count} 消息, "
                f"压缩比: {result.compression_ratio:.2f}, 策略: {result.metadata.get('strategy', 'unknown')}"
            )
            return result
        except Exception as e:
            logger.error(f"上下文压缩失败: {e}")
            # 返回原始消息作为fallback
            return CompressionResult(
                compressed_messages=messages,
                original_count=len(messages),
                compressed_count=len(messages),
                compression_ratio=1.0,
                preserved_tokens=self._compressor._calculate_messages_tokens(messages),
                metadata={"strategy": "fallback", "error": str(e)}
            )


def create_token_calculator(
    strategy: TokenCalculationStrategy = TokenCalculationStrategy.ESTIMATE,
    api_base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    tokenizer_cache_dir: Optional[str] = None
) -> TokenCalculator:
    """创建token计算器的工厂函数
    
    Args:
        strategy: token计算策略
        api_base_url: API基础URL（仅API策略需要）
        api_key: API密钥（仅API策略需要）
        model_name: 模型名称
        tokenizer_cache_dir: tokenizer缓存目录（仅transformers策略需要）
        
    Returns:
        TokenCalculator: token计算器实例
    """
    if strategy == TokenCalculationStrategy.ESTIMATE:
        return EstimateTokenCalculator()
    elif strategy == TokenCalculationStrategy.API:
        if not api_base_url or not api_key:
            raise ValueError("API token计算需要配置api_base_url和api_key")
        if not model_name:
            raise ValueError("API token计算需要指定model_name")
        return APITokenCalculator(
            api_base_url=api_base_url,
            api_key=api_key,
            model_name=model_name
        )
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
    
    def update_config(self, config: CompressionConfig):
        """更新压缩配置"""
        self.config = config
        self._compressor = self._create_compressor()
    
    def get_compression_stats(self, messages: List[Message]) -> Dict[str, Any]:
        """获取压缩统计信息"""
        current_tokens = self._compressor._calculate_messages_tokens(messages)
        return {
            "total_messages": len(messages),
            "estimated_tokens": current_tokens,
            "needs_compression": current_tokens > self.config.max_tokens,
            "compression_threshold": self.config.max_tokens,
            "strategy": self.config.strategy.value
        }