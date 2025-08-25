#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
关键信息提取压缩器模块

基于关键信息提取的压缩策略。
"""

import re
from typing import List, Set

from echo.llms.schema import Message
from echo.agents.core.token_calculator import TokenCalculator
from echo.config import CompressionConfig
from .base import BaseCompressor, CompressionResult


class KeyExtractionCompressor(BaseCompressor):
    """关键信息提取压缩器"""
    
    def __init__(self, config: CompressionConfig, token_calculator: TokenCalculator, min_content_length: int = 200):
        super().__init__(config, token_calculator)
        self.min_content_length = min_content_length
        
        # 关键词模式
        self.key_patterns = [
            # 中文关键词
            r"\b(?:重要|关键|核心|主要|必须|需要|要求|目标|结果|结论|决定|确定)\b",
            r"\b(?:问题|错误|异常|失败|成功|完成|解决|报错)\b",
            r"\b(?:API|接口|函数|方法|类|模块|文件|数据库|配置)\b",
            r"\b(?:用户|客户|需求|功能|特性|版本|更新)\b",
            
            # 英文关键词
            r"\b(?:important|critical|key|main|major|essential|required|necessary|must|should|goal|target|result|conclusion|decision|determine)\b",
            r"\b(?:error|exception|failure|failed|success|successful|complete|completed|solve|solved|fix|fixed|issue|problem|bug|warning)\b",
            r"\b(?:API|interface|function|method|class|module|file|database|config|configuration|library|framework|package)\b",
            r"\b(?:user|client|customer|requirement|feature|functionality|version|update|upgrade|deploy|deployment)\b",
            
            # 代码相关英文关键词
            r"\b(?:syntax|runtime|compile|compilation|build|test|testing|debug|debugging|trace|traceback|stack)\b",
            r"\b(?:import|export|return|throw|catch|try|except|finally|async|await|promise|callback)\b",
            r"\b(?:undefined|null|none|empty|missing|not found|invalid|timeout|connection|network)\b"
        ]
    
    def compress(self, messages: List[Message]) -> CompressionResult:
        """使用关键信息提取进行压缩"""
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
        
        if not messages_to_process:
            return CompressionResult(
                compressed_messages=messages,
                original_count=len(messages),
                compressed_count=len(messages),
                compression_ratio=1.0,
                preserved_tokens=self._calculate_messages_tokens(messages),
                metadata={"strategy": "key_extraction", "reason": "insufficient_messages"}
            )
        
        # 提取关键信息
        key_messages = self._extract_key_messages(messages_to_process)
        
        # 构建压缩后的消息列表
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
        """提取关键消息"""
        key_messages = []
        
        for message in messages:
            content = message.get("content", "")
            if self._is_key_message(content):
                key_messages.append(message)
        
        # 如果没有找到关键消息，保留一些重要的消息
        if not key_messages and messages:
            # 保留系统消息和较长的用户消息
            for message in messages:
                role = message.get("role", "")
                content = message.get("content", "")
                
                if role == "system" or (role == "user" and len(content) > 50):
                    key_messages.append(message)
                    if len(key_messages) >= 3:  # 最多保留3条
                        break
        
        return key_messages
    

    
    def _contains_key_info(self, text: str) -> bool:
        """检查文本是否包含关键信息
        
        Args:
            text: 要检查的文本
            
        Returns:
            bool: 是否包含关键信息
        """
        if not text:
            return False
        
        # 检查关键词模式
        for pattern in self.key_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        # 检查是否包含代码块
        if "```" in text or "`" in text:
            return True
        
        # 检查是否包含URL或文件路径
        if re.search(r"https?://|/[\w/.-]+|\w+\.[\w.]+", text):
            return True
        
        # 检查英文错误信息模式
        error_patterns = [
            r"\b(?:Error|Exception|Warning|Fatal|Critical)\b.*?:\s*",
            r"\b(?:at|in)\s+[\w.]+\([^)]*\)\s*",  # 堆栈跟踪
            r"\b(?:line|Line)\s+\d+",  # 行号信息
            r"\b(?:Expected|Unexpected|Cannot|Unable|Failed to)\b",
            r"\b(?:TypeError|ValueError|AttributeError|ImportError|SyntaxError|NameError)\b"
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        # 检查技术文档关键标识
        doc_patterns = [
            r"\b(?:Parameters?|Arguments?|Returns?|Example|Usage|Note|Warning|See also)\s*:",
            r"\b(?:@param|@return|@throws|@see|@example|@deprecated)\b",
            r"\b(?:TODO|FIXME|NOTE|WARNING|DEPRECATED)\b",
            r"\b(?:version|v\d+\.\d+|release|changelog)\b"
        ]
        
        for pattern in doc_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _is_key_message(self, content: str) -> bool:
        """判断是否为关键消息
        
        Args:
            content: 消息内容
            
        Returns:
            bool: 是否为关键消息
        """
        if not content:
            return False
        
        # 检查是否包含关键信息
        if self._contains_key_info(content):
            return True
        
        # 检查消息长度（较长的消息可能包含重要信息）
        if len(content) > self.min_content_length:
            return True
        
        return False