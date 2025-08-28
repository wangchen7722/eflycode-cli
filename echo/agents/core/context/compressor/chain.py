#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
压缩器链模块

实现压缩器链模式，允许用户通过配置指定多个压缩器的执行顺序。
"""

from typing import List, Optional, Dict, Any, Type
from enum import Enum

from echo.llms.schema import Message
from echo.llms.llm_engine import LLMEngine
from echo.agents.core.token_calculator import TokenCalculator
from echo.config import CompressionConfig
from echo.utils.logger import get_logger
from .base import BaseCompressor, CompressionResult
from .summary import SummaryCompressor
from .sliding_window import SlidingWindowCompressor
from .key_extraction import KeyExtractionCompressor

logger = get_logger()


class CompressorType(Enum):
    """压缩器类型枚举"""
    SUMMARY = "summary"
    SLIDING_WINDOW = "sliding_window"
    KEY_EXTRACTION = "key_extraction"


class CompressorChainConfig:
    """压缩器链配置"""
    
    def __init__(self, compressor_types: List[CompressorType], selection_strategy: str = "best_ratio"):
        self.compressor_types = compressor_types
        self.selection_strategy = selection_strategy


class CompressorChain(BaseCompressor):
    """压缩器链
    
    支持配置多个压缩器，根据策略选择最佳压缩结果。
    """
    
    def __init__(self, 
                 config: CompressionConfig, 
                 token_calculator: TokenCalculator, 
                 chain_config: CompressorChainConfig,
                 llm_engine: Optional[LLMEngine] = None):
        super().__init__(config, token_calculator)
        self.llm_engine = llm_engine
        self.chain_config = chain_config
        
        # 压缩器类型映射
        self._compressor_classes: Dict[CompressorType, Type[BaseCompressor]] = {
            CompressorType.SUMMARY: SummaryCompressor,
            CompressorType.SLIDING_WINDOW: SlidingWindowCompressor,
            CompressorType.KEY_EXTRACTION: KeyExtractionCompressor,
        }
        
        # 初始化压缩器实例
        self.compressors = self._create_compressors()
    
    def _create_compressors(self) -> List[BaseCompressor]:
        """根据配置创建压缩器实例"""
        compressors = []
        
        for compressor_type in self.chain_config.compressor_types:
            compressor_class = self._compressor_classes.get(compressor_type)
            if not compressor_class:
                logger.warning(f"未知的压缩器类型: {compressor_type}")
                continue
            
            try:
                if compressor_type == CompressorType.SUMMARY:
                    if not self.llm_engine:
                        logger.warning("摘要压缩器需要LLM引擎，跳过")
                        continue
                    compressor = compressor_class(self.config, self.token_calculator, self.llm_engine)
                else:
                    compressor = compressor_class(self.config, self.token_calculator)
                
                compressors.append(compressor)
                logger.info(f"已创建压缩器: {compressor_type.value}")
                
            except Exception as e:
                logger.error(f"创建压缩器失败 {compressor_type.value}: {e}")
                continue
        
        if not compressors:
            logger.warning("没有可用的压缩器，创建默认滑动窗口压缩器")
            compressors.append(SlidingWindowCompressor(self.config, self.token_calculator))
        
        return compressors
    
    def compress(self, messages: List[Message]) -> CompressionResult:
        """使用链中的压缩器进行压缩"""
        if len(messages) < self.config.min_messages_to_compress:
            return CompressionResult(
                compressed_messages=messages,
                original_count=len(messages),
                compressed_count=len(messages),
                compression_ratio=1.0,
                preserved_tokens=self._calculate_messages_tokens(messages),
                metadata={"strategy": "chain", "reason": "insufficient_messages"}
            )
        
        # 使用所有压缩器进行压缩
        results = []
        for compressor in self.compressors:
            try:
                result = compressor.compress(messages)
                result.metadata["compressor_type"] = compressor.__class__.__name__
                results.append(result)
                logger.debug(f"压缩器 {compressor.__class__.__name__} 完成，压缩比: {result.compression_ratio:.3f}")
            except Exception as e:
                logger.error(f"压缩器 {compressor.__class__.__name__} 执行失败: {e}")
                continue
        
        if not results:
            logger.error("所有压缩器都执行失败，返回原始消息")
            return CompressionResult(
                compressed_messages=messages,
                original_count=len(messages),
                compressed_count=len(messages),
                compression_ratio=1.0,
                preserved_tokens=self._calculate_messages_tokens(messages),
                metadata={"strategy": "chain", "reason": "all_compressors_failed"}
            )
        
        # 根据策略选择最佳结果
        best_result = self._select_best_result(results)
        best_result.metadata["chain_strategy"] = self.chain_config.selection_strategy
        best_result.metadata["total_compressors"] = len(self.compressors)
        best_result.metadata["successful_compressors"] = len(results)
        
        return best_result
    
    def _select_best_result(self, results: List[CompressionResult]) -> CompressionResult:
        """根据策略选择最佳压缩结果"""
        if not results:
            raise ValueError("没有压缩结果可供选择")
        
        if self.chain_config.selection_strategy == "best_ratio":
            return self._select_by_compression_ratio(results)
        elif self.chain_config.selection_strategy == "best_score":
            return self._select_by_score(results)
        elif self.chain_config.selection_strategy == "most_messages":
            return self._select_by_message_count(results)
        else:
            logger.warning(f"未知的选择策略: {self.chain_config.selection_strategy}，使用默认策略")
            return self._select_by_compression_ratio(results)
    
    def _select_by_compression_ratio(self, results: List[CompressionResult]) -> CompressionResult:
        """根据压缩比选择最佳结果，压缩比越小越好"""
        return min(results, key=lambda r: r.compression_ratio)
    
    def _select_by_score(self, results: List[CompressionResult]) -> CompressionResult:
        """根据综合评分选择最佳结果"""
        best_result = results[0]
        best_score = self._calculate_result_score(best_result)
        
        for result in results[1:]:
            score = self._calculate_result_score(result)
            if score > best_score:
                best_result = result
                best_score = score
        
        return best_result
    
    def _select_by_message_count(self, results: List[CompressionResult]) -> CompressionResult:
        """根据保留消息数量选择最佳结果，保留更多消息的结果更好"""
        return max(results, key=lambda r: r.compressed_count)
    
    def _calculate_result_score(self, result: CompressionResult) -> float:
        """计算压缩结果的综合评分"""
        # 压缩比权重，越小越好
        compression_score = 1.0 - result.compression_ratio
        
        # 保留消息数量权重
        message_score = min(result.compressed_count / self.config.preserve_recent_messages, 1.0)
        
        # 综合评分
        return compression_score * 0.7 + message_score * 0.3
    
    def add_compressor(self, compressor_type: CompressorType):
        """动态添加压缩器"""
        if compressor_type in self.chain_config.compressor_types:
            logger.warning(f"压缩器类型 {compressor_type.value} 已存在")
            return
        
        self.chain_config.compressor_types.append(compressor_type)
        self.compressors = self._create_compressors()
        logger.info(f"已添加压缩器: {compressor_type.value}")
    
    def remove_compressor(self, compressor_type: CompressorType):
        """动态移除压缩器"""
        if compressor_type not in self.chain_config.compressor_types:
            logger.warning(f"压缩器类型 {compressor_type.value} 不存在")
            return
        
        self.chain_config.compressor_types.remove(compressor_type)
        self.compressors = self._create_compressors()
        logger.info(f"已移除压缩器: {compressor_type.value}")
    
    def get_compressor_info(self) -> Dict[str, Any]:
        """获取压缩器链信息"""
        return {
            "compressor_types": [ct.value for ct in self.chain_config.compressor_types],
            "selection_strategy": self.chain_config.selection_strategy,
            "active_compressors": len(self.compressors),
            "compressor_classes": [c.__class__.__name__ for c in self.compressors]
        }