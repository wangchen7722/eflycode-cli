"""Token 计算模块

基于 tiktoken 实现 token 数量计算
"""

from typing import List

import tiktoken
from tiktoken import Encoding

from eflycode.core.llm.protocol import Message


class Tokenizer:
    """Token 计算器，基于 tiktoken"""

    # 模型到编码器的映射
    MODEL_ENCODING_MAP = {
        # 默认编码器
        "default": "cl100k_base",
    }

    def __init__(self):
        """初始化 Tokenizer"""
        self._encodings: dict[str, Encoding] = {}

    def get_encoding_for_model(self, model: str) -> Encoding:
        """获取模型的编码器

        Args:
            model: 模型名称

        Returns:
            Encoding: tiktoken 编码器
        """
        # 查找模型对应的编码器名称
        encoding_name = self.MODEL_ENCODING_MAP.get(model, self.MODEL_ENCODING_MAP["default"])
        
        # 如果模型名称包含编码器名称，直接使用
        for known_model, enc_name in self.MODEL_ENCODING_MAP.items():
            if known_model in model.lower():
                encoding_name = enc_name
                break

        # 缓存编码器
        if encoding_name not in self._encodings:
            try:
                self._encodings[encoding_name] = tiktoken.get_encoding(encoding_name)
            except Exception:
                # 如果获取失败，使用默认编码器
                encoding_name = self.MODEL_ENCODING_MAP["default"]
                self._encodings[encoding_name] = tiktoken.get_encoding(encoding_name)

        return self._encodings[encoding_name]

    def count_message_tokens(self, message: Message, model: str) -> int:
        """计算单条消息的 token 数

        Args:
            message: 消息对象
            model: 模型名称

        Returns:
            int: token 数量
        """
        encoding = self.get_encoding_for_model(model)
        tokens = 0

        # 计算 role 的 token（通常每个 role 是 1-2 个 token）
        if message.role:
            tokens += len(encoding.encode(message.role))

        # 计算 content 的 token
        if message.content:
            tokens += len(encoding.encode(message.content))

        # 计算 tool_calls 的 token（如果有）
        if message.tool_calls:
            for tool_call in message.tool_calls:
                if tool_call.function:
                    if tool_call.function.name:
                        tokens += len(encoding.encode(tool_call.function.name))
                    if tool_call.function.arguments:
                        tokens += len(encoding.encode(tool_call.function.arguments))

        # 计算 tool_call_id 的 token（如果有）
        if message.tool_call_id:
            tokens += len(encoding.encode(message.tool_call_id))

        # 每条消息有额外的格式 token（大约 3-4 个）
        tokens += 4

        return tokens

    def count_tokens(self, messages: List[Message], model: str) -> int:
        """计算消息列表的 token 数

        Args:
            messages: 消息列表
            model: 模型名称

        Returns:
            int: 总 token 数量
        """
        total = 0
        for message in messages:
            total += self.count_message_tokens(message, model)
        return total

