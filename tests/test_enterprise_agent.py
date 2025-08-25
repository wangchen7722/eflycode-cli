#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
企业级Agent测试用例

测试Agent的上下文压缩、检索、记忆管理等企业级功能
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from echo.agents.core.agent import Agent
from echo.agents.core.context_compressor import ContextCompressor
from echo.agents.core.context_retriever import ContextRetriever
from echo.agents.core.memory_manager import MemoryManager
from echo.config import (
    CompressionStrategy, CompressionConfig,
    RetrievalStrategy, RetrievalConfig,
    MemoryType, MemoryImportance, MemoryConfig
)
from echo.llm.base import BaseLLM
from echo.tools.base import BaseTool


class MockLLM(BaseLLM):
    """模拟LLM用于测试"""
    
    def __init__(self):
        super().__init__()
        self.model_name = "mock-llm"
    
    def generate(self, messages, **kwargs):
        return "Mock response"
    
    def generate_stream(self, messages, **kwargs):
        yield "Mock "
        yield "stream "
        yield "response"


class MockTool(BaseTool):
    """模拟工具用于测试"""
    
    def __init__(self):
        super().__init__()
        self.name = "mock_tool"
        self.description = "A mock tool for testing"
    
    def execute(self, **kwargs):
        return f"Mock tool executed with {kwargs}"


class TestEnterpriseAgent:
    """企业级Agent测试类"""
    
    @pytest.fixture
    def mock_llm(self):
        return MockLLM()
    
    @pytest.fixture
    def mock_tool(self):
        return MockTool()
    
    @pytest.fixture
    def compression_config(self):
        return CompressionConfig(
            strategy=CompressionStrategy.SUMMARY,
            max_tokens=1000,
            compression_ratio=0.5
        )
    
    @pytest.fixture
    def retrieval_config(self):
        return RetrievalConfig(
            strategy=RetrievalStrategy.SEMANTIC,
            max_results=5,
            similarity_threshold=0.7
        )
    
    @pytest.fixture
    def memory_config(self):
        return MemoryConfig(
            max_short_term_memories=100,
            max_long_term_memories=1000,
            consolidation_threshold=timedelta(hours=24)
        )
    
    @pytest.fixture
    def enterprise_agent(self, mock_llm, mock_tool, compression_config, 
                        retrieval_config, memory_config):
        """创建企业级Agent实例"""
        return Agent(
            name="EnterpriseAgent",
            description="企业级代码助手",
            llm=mock_llm,
            tools=[mock_tool],
            compression_config=compression_config,
            retrieval_config=retrieval_config,
            memory_config=memory_config
        )
    
    def test_agent_initialization(self, enterprise_agent):
        """测试Agent初始化"""
        assert enterprise_agent.name == "EnterpriseAgent"
        assert enterprise_agent.description == "企业级代码助手"
        assert enterprise_agent.enable_context_compression is True
        assert enterprise_agent.enable_context_retrieval is True
        assert enterprise_agent.enable_memory_management is True
        assert enterprise_agent.context_compressor is not None
        assert enterprise_agent.context_retriever is not None
        assert enterprise_agent.memory_manager is not None
    
    def test_memory_operations(self, enterprise_agent):
        """测试记忆操作"""
        # 添加记忆
        memory_id = enterprise_agent.add_to_memory(
            "这是一个测试记忆",
            memory_type=MemoryType.SHORT_TERM,
            importance=MemoryImportance.HIGH,
            tags={"test", "memory"}
        )
        assert memory_id is not None
        
        # 搜索记忆
        results = enterprise_agent.search_memory("测试")
        assert len(results) > 0
        
        # 整合记忆
        consolidated = enterprise_agent.consolidate_memories()
        assert isinstance(consolidated, int)
        
        # 清理记忆
        cleaned = enterprise_agent.cleanup_memories()
        assert isinstance(cleaned, int)
    
    def test_agent_stats(self, enterprise_agent):
        """测试Agent统计信息"""
        stats = enterprise_agent.get_agent_stats()
        
        assert "name" in stats
        assert "description" in stats
        assert "tools_count" in stats
        assert "available_tools" in stats
        assert "conversation_length" in stats
        assert "features" in stats
        
        features = stats["features"]
        assert features["context_compression"] is True
        assert features["context_retrieval"] is True
        assert features["memory_management"] is True
    
    def test_configuration_updates(self, enterprise_agent):
        """测试配置更新"""
        # 更新压缩配置
        new_compression_config = CompressionConfig(
            strategy=CompressionStrategy.SLIDING_WINDOW,
            max_tokens=2000,
            compression_ratio=0.3
        )
        enterprise_agent.update_compression_config(new_compression_config)
        assert enterprise_agent.compression_config.strategy == CompressionStrategy.SLIDING_WINDOW
        
        # 更新检索配置
        new_retrieval_config = RetrievalConfig(
            strategy=RetrievalStrategy.KEYWORD,
            max_results=10,
            similarity_threshold=0.8
        )
        enterprise_agent.update_retrieval_config(new_retrieval_config)
        assert enterprise_agent.retrieval_config.strategy == RetrievalStrategy.KEYWORD
    
    def test_conversation_management(self, enterprise_agent):
        """测试对话管理"""
        # 添加一些对话历史
        enterprise_agent._history_messages.extend([
            {"role": "user", "content": "Hello", "timestamp": datetime.now()},
            {"role": "assistant", "content": "Hi there!", "timestamp": datetime.now()}
        ])
        
        # 导出对话
        exported = enterprise_agent.export_conversation()
        assert len(exported) == 2
        assert exported[0]["role"] == "user"
        assert exported[0]["content"] == "Hello"
        
        # 清空对话历史
        enterprise_agent.clear_conversation_history()
        assert len(enterprise_agent._history_messages) == 0
        
        # 导入对话
        enterprise_agent.import_conversation(exported)
        assert len(enterprise_agent._history_messages) == 2
    
    @patch('echo.agents.core.agent.logger')
    def test_memory_disabled_warnings(self, mock_logger, mock_llm, mock_tool):
        """测试记忆功能禁用时的警告"""
        # 创建没有记忆管理的Agent
        agent = Agent(
            name="SimpleAgent",
            description="简单Agent",
            llm=mock_llm,
            tools=[mock_tool]
        )
        
        # 尝试使用记忆功能
        result = agent.add_to_memory("test")
        assert result is None
        mock_logger.warning.assert_called_with("记忆管理器未启用")
        
        results = agent.search_memory("test")
        assert results == []
    
    def test_context_compression_integration(self, enterprise_agent):
        """测试上下文压缩集成"""
        # 添加足够多的消息触发压缩
        for i in range(10):
            enterprise_agent._history_messages.append({
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"Message {i}",
                "timestamp": datetime.now()
            })
        
        # 预处理消息应该触发压缩
        original_length = len(enterprise_agent._history_messages)
        processed_messages = enterprise_agent._preprocess_messages()
        
        # 验证压缩是否生效（消息数量应该减少或保持在合理范围内）
        assert len(processed_messages) <= original_length
    
    @patch('echo.agents.core.agent.Agent._run_no_stream')
    def test_run_with_memory_integration(self, mock_run, enterprise_agent):
        """测试运行时的记忆集成"""
        mock_run.return_value = "Mock response"
        
        # 运行Agent
        response = enterprise_agent.run("测试用户输入")
        
        # 验证用户输入被添加到记忆
        memories = enterprise_agent.search_memory("测试用户输入")
        assert len(memories) > 0
    
    def test_tool_execution_with_memory(self, enterprise_agent):
        """测试工具执行时的记忆记录"""
        # 执行工具
        result = enterprise_agent.execute_tool("mock_tool", {"param": "value"})
        
        # 验证工具执行被记录到记忆
        memories = enterprise_agent.search_memory("mock_tool")
        assert len(memories) > 0


class TestContextCompressor:
    """上下文压缩器测试"""
    
    def test_summary_compression(self):
        """测试摘要压缩"""
        config = CompressionConfig(
            strategy=CompressionStrategy.SUMMARY,
            max_tokens=100
        )
        compressor = ContextCompressor(config)
        
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "I'm doing well, thank you!"}
        ]
        
        result = compressor.compress(messages)
        assert result.compressed_messages is not None
        assert result.compression_ratio > 0
    
    def test_sliding_window_compression(self):
        """测试滑动窗口压缩"""
        config = CompressionConfig(
            strategy=CompressionStrategy.SLIDING_WINDOW,
            max_messages=2
        )
        compressor = ContextCompressor(config)
        
        messages = [
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Message 2"},
            {"role": "assistant", "content": "Response 2"},
            {"role": "user", "content": "Message 3"}
        ]
        
        result = compressor.compress(messages)
        assert len(result.compressed_messages) <= 2


class TestContextRetriever:
    """上下文检索器测试"""
    
    def test_keyword_retrieval(self):
        """测试关键词检索"""
        config = RetrievalConfig(
            strategy=RetrievalStrategy.KEYWORD,
            max_results=3
        )
        retriever = ContextRetriever(config)
        
        messages = [
            {"role": "user", "content": "Python编程问题"},
            {"role": "assistant", "content": "我可以帮助您解决Python问题"},
            {"role": "user", "content": "JavaScript函数"},
            {"role": "assistant", "content": "JavaScript函数的定义方法"}
        ]
        
        result = retriever.retrieve("Python", messages)
        assert len(result.retrieved_contexts) > 0
        assert result.relevance_scores is not None


class TestMemoryManager:
    """记忆管理器测试"""
    
    def test_memory_operations(self):
        """测试记忆操作"""
        config = MemoryConfig(
            max_short_term_memories=10,
            max_long_term_memories=100
        )
        manager = MemoryManager(config)
        
        # 添加记忆
        memory_id = manager.add_memory(
            "测试记忆内容",
            MemoryType.SHORT_TERM,
            MemoryImportance.HIGH
        )
        assert memory_id is not None
        
        # 搜索记忆
        results = manager.search_memories("测试")
        assert len(results) > 0
        
        # 获取统计信息
        stats = manager.get_memory_stats()
        assert "total_memories" in stats
        assert "short_term_count" in stats
        assert "long_term_count" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])