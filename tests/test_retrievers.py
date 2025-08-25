#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检索器测试用例"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from echo.agents.core.context.retriever import (
    BaseRetriever,
    RetrievalResult,
    SemanticRetriever,
    KeywordRetriever,
    HybridRetriever,
    TimeBasedRetriever,
    create_retriever
)
from echo.llms.schema import Message
from echo.config import RetrievalConfig, RetrievalStrategy


class TestRetrievalResult(unittest.TestCase):
    """检索结果测试"""
    
    def test_retrieval_result_creation(self):
        """测试检索结果创建"""
        messages = [Message(role="user", content="test")]
        result = RetrievalResult(
            retrieved_messages=messages,
            relevance_scores=[0.8],
            total_candidates=10,
            metadata={"strategy": "test"}
        )
        
        self.assertEqual(result.retrieved_messages, messages)
        self.assertEqual(result.relevance_scores, [0.8])
        self.assertEqual(result.total_candidates, 10)
        self.assertEqual(result.metadata["strategy"], "test")
    
    def test_retrieval_result_with_empty_scores(self):
        """测试空相关性分数的检索结果"""
        messages = [Message(role="user", content="test")]
        result = RetrievalResult(
            retrieved_messages=messages,
            relevance_scores=None,
            total_candidates=1
        )
        
        self.assertEqual(result.relevance_scores, [])


class TestSemanticRetriever(unittest.TestCase):
    """语义检索器测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_embedding_model = Mock()
        self.config = RetrievalConfig(
            strategy=RetrievalStrategy.SEMANTIC,
            max_results=5,
            similarity_threshold=0.7
        )
        self.retriever = SemanticRetriever(self.mock_embedding_model, self.config)
    
    def test_retrieve_empty_context(self):
        """测试空上下文检索"""
        result = self.retriever.retrieve("query", [])
        
        self.assertEqual(result.retrieved_messages, [])
        self.assertEqual(result.relevance_scores, [])
        self.assertEqual(result.total_candidates, 0)
    
    def test_retrieve_with_similarity(self):
        """测试基于相似度的检索"""
        messages = [
            Message(role="user", content="How to use Python?"),
            Message(role="assistant", content="Python is a programming language"),
            Message(role="user", content="What is machine learning?"),
            Message(role="assistant", content="ML is a subset of AI")
        ]
        
        # 模拟嵌入向量
        query_embedding = [0.1, 0.2, 0.3]
        message_embeddings = [
            [0.1, 0.2, 0.3],  # 高相似度
            [0.1, 0.2, 0.2],  # 中等相似度
            [0.5, 0.6, 0.7],  # 低相似度
            [0.4, 0.5, 0.6]   # 低相似度
        ]
        
        self.mock_embedding_model.encode.side_effect = [query_embedding] + message_embeddings
        
        result = self.retriever.retrieve("Python programming", messages)
        
        # 验证结果
        self.assertGreater(len(result.retrieved_messages), 0)
        self.assertEqual(len(result.retrieved_messages), len(result.relevance_scores))
        self.assertEqual(result.total_candidates, len(messages))
        
        # 验证相关性分数是降序排列的
        scores = result.relevance_scores
        self.assertEqual(scores, sorted(scores, reverse=True))
    
    def test_cosine_similarity(self):
        """测试余弦相似度计算"""
        vec1 = [1, 0, 0]
        vec2 = [0, 1, 0]
        vec3 = [1, 0, 0]
        
        # 垂直向量相似度为0
        similarity1 = self.retriever._cosine_similarity(vec1, vec2)
        self.assertAlmostEqual(similarity1, 0.0, places=5)
        
        # 相同向量相似度为1
        similarity2 = self.retriever._cosine_similarity(vec1, vec3)
        self.assertAlmostEqual(similarity2, 1.0, places=5)
    
    def test_similarity_threshold_filtering(self):
        """测试相似度阈值过滤"""
        messages = [
            Message(role="user", content="Test message 1"),
            Message(role="user", content="Test message 2")
        ]
        
        # 模拟低相似度嵌入
        query_embedding = [1, 0, 0]
        message_embeddings = [
            [0, 1, 0],  # 相似度 = 0 < 0.7
            [0, 0, 1]   # 相似度 = 0 < 0.7
        ]
        
        self.mock_embedding_model.encode.side_effect = [query_embedding] + message_embeddings
        
        result = self.retriever.retrieve("query", messages)
        
        # 所有消息都应该被过滤掉
        self.assertEqual(len(result.retrieved_messages), 0)
        self.assertEqual(len(result.relevance_scores), 0)


class TestKeywordRetriever(unittest.TestCase):
    """关键词检索器测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.config = RetrievalConfig(
            strategy=RetrievalStrategy.KEYWORD,
            max_results=3
        )
        self.retriever = KeywordRetriever(self.config)
    
    def test_retrieve_exact_match(self):
        """测试精确匹配检索"""
        messages = [
            Message(role="user", content="How to use Python for data analysis?"),
            Message(role="assistant", content="You can use pandas library"),
            Message(role="user", content="What about machine learning?"),
            Message(role="assistant", content="Try scikit-learn for ML")
        ]
        
        result = self.retriever.retrieve("Python data", messages)
        
        # 应该找到包含"Python"和"data"的消息
        self.assertGreater(len(result.retrieved_messages), 0)
        self.assertTrue(any("Python" in msg.content for msg in result.retrieved_messages))
    
    def test_retrieve_case_insensitive(self):
        """测试大小写不敏感检索"""
        messages = [
            Message(role="user", content="PYTHON programming"),
            Message(role="assistant", content="python is great")
        ]
        
        result = self.retriever.retrieve("Python", messages)
        
        # 应该找到两条消息（大小写不敏感）
        self.assertEqual(len(result.retrieved_messages), 2)
    
    def test_calculate_keyword_score(self):
        """测试关键词分数计算"""
        keywords = ["python", "data"]
        
        # 包含所有关键词的消息
        message1 = Message(role="user", content="Python is great for data analysis")
        score1 = self.retriever._calculate_keyword_score(message1, keywords)
        
        # 只包含部分关键词的消息
        message2 = Message(role="user", content="Python is a programming language")
        score2 = self.retriever._calculate_keyword_score(message2, keywords)
        
        # 不包含关键词的消息
        message3 = Message(role="user", content="Java is also good")
        score3 = self.retriever._calculate_keyword_score(message3, keywords)
        
        self.assertGreater(score1, score2)
        self.assertGreater(score2, score3)
        self.assertEqual(score3, 0)
    
    def test_extract_keywords(self):
        """测试关键词提取"""
        query = "How to use Python for data analysis?"
        keywords = self.retriever._extract_keywords(query)
        
        # 应该提取出有意义的关键词
        self.assertIn("python", keywords)
        self.assertIn("data", keywords)
        self.assertIn("analysis", keywords)
        
        # 不应该包含停用词
        self.assertNotIn("how", keywords)
        self.assertNotIn("to", keywords)
        self.assertNotIn("for", keywords)


class TestHybridRetriever(unittest.TestCase):
    """混合检索器测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_embedding_model = Mock()
        self.config = RetrievalConfig(
            strategy=RetrievalStrategy.HYBRID,
            max_results=5,
            similarity_threshold=0.5
        )
        self.retriever = HybridRetriever(self.mock_embedding_model, self.config)
    
    @patch('echo.agents.core.context.retriever.hybrid.SemanticRetriever')
    @patch('echo.agents.core.context.retriever.hybrid.KeywordRetriever')
    def test_retrieve_combines_results(self, mock_keyword_class, mock_semantic_class):
        """测试混合检索结合结果"""
        messages = [
            Message(role="user", content="Python programming"),
            Message(role="assistant", content="Data analysis with pandas")
        ]
        
        # 模拟语义检索结果
        semantic_result = RetrievalResult(
            retrieved_messages=[messages[0]],
            relevance_scores=[0.8],
            total_candidates=2
        )
        mock_semantic_retriever = Mock()
        mock_semantic_retriever.retrieve.return_value = semantic_result
        mock_semantic_class.return_value = mock_semantic_retriever
        
        # 模拟关键词检索结果
        keyword_result = RetrievalResult(
            retrieved_messages=[messages[1]],
            relevance_scores=[0.6],
            total_candidates=2
        )
        mock_keyword_retriever = Mock()
        mock_keyword_retriever.retrieve.return_value = keyword_result
        mock_keyword_class.return_value = mock_keyword_retriever
        
        result = self.retriever.retrieve("Python data", messages)
        
        # 验证两个检索器都被调用
        mock_semantic_retriever.retrieve.assert_called_once_with("Python data", messages)
        mock_keyword_retriever.retrieve.assert_called_once_with("Python data", messages)
        
        # 验证结果被合并
        self.assertEqual(len(result.retrieved_messages), 2)
    
    def test_combine_results_removes_duplicates(self):
        """测试结果合并时去重"""
        message = Message(role="user", content="Test message")
        
        semantic_result = RetrievalResult(
            retrieved_messages=[message],
            relevance_scores=[0.8],
            total_candidates=1
        )
        
        keyword_result = RetrievalResult(
            retrieved_messages=[message],  # 相同消息
            relevance_scores=[0.6],
            total_candidates=1
        )
        
        combined = self.retriever._combine_results(semantic_result, keyword_result)
        
        # 应该只有一条消息（去重）
        self.assertEqual(len(combined.retrieved_messages), 1)
        self.assertEqual(combined.retrieved_messages[0], message)
        # 应该使用更高的分数
        self.assertEqual(combined.relevance_scores[0], 0.8)
    
    def test_combine_results_sorts_by_score(self):
        """测试结果按分数排序"""
        message1 = Message(role="user", content="Message 1")
        message2 = Message(role="user", content="Message 2")
        
        semantic_result = RetrievalResult(
            retrieved_messages=[message1],
            relevance_scores=[0.6],
            total_candidates=2
        )
        
        keyword_result = RetrievalResult(
            retrieved_messages=[message2],
            relevance_scores=[0.8],
            total_candidates=2
        )
        
        combined = self.retriever._combine_results(semantic_result, keyword_result)
        
        # 应该按分数降序排列
        self.assertEqual(combined.retrieved_messages[0], message2)  # 0.8分
        self.assertEqual(combined.retrieved_messages[1], message1)  # 0.6分
        self.assertEqual(combined.relevance_scores, [0.8, 0.6])


class TestTimeBasedRetriever(unittest.TestCase):
    """时间检索器测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.config = RetrievalConfig(
            strategy=RetrievalStrategy.TIME_BASED,
            max_results=3,
            time_window_hours=24
        )
        self.retriever = TimeBasedRetriever(self.config)
    
    def test_retrieve_recent_messages(self):
        """测试检索最近消息"""
        now = datetime.now()
        messages = [
            Message(role="user", content="Old message", timestamp=now - timedelta(hours=48)),
            Message(role="user", content="Recent message 1", timestamp=now - timedelta(hours=12)),
            Message(role="user", content="Recent message 2", timestamp=now - timedelta(hours=6)),
            Message(role="user", content="Very recent", timestamp=now - timedelta(hours=1))
        ]
        
        result = self.retriever.retrieve("query", messages)
        
        # 应该只返回24小时内的消息
        self.assertEqual(len(result.retrieved_messages), 3)
        
        # 验证都是最近的消息
        for msg in result.retrieved_messages:
            time_diff = now - msg.timestamp
            self.assertLessEqual(time_diff.total_seconds(), 24 * 3600)
    
    def test_retrieve_sorts_by_recency(self):
        """测试按时间新旧排序"""
        now = datetime.now()
        messages = [
            Message(role="user", content="Message 1", timestamp=now - timedelta(hours=12)),
            Message(role="user", content="Message 2", timestamp=now - timedelta(hours=6)),
            Message(role="user", content="Message 3", timestamp=now - timedelta(hours=1))
        ]
        
        result = self.retriever.retrieve("query", messages)
        
        # 应该按时间降序排列（最新的在前）
        timestamps = [msg.timestamp for msg in result.retrieved_messages]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))
    
    def test_retrieve_with_no_timestamp(self):
        """测试处理没有时间戳的消息"""
        messages = [
            Message(role="user", content="No timestamp"),  # 没有时间戳
            Message(role="user", content="With timestamp", timestamp=datetime.now())
        ]
        
        result = self.retriever.retrieve("query", messages)
        
        # 应该只返回有时间戳的消息
        self.assertEqual(len(result.retrieved_messages), 1)
        self.assertEqual(result.retrieved_messages[0].content, "With timestamp")
    
    def test_calculate_recency_score(self):
        """测试时间新旧分数计算"""
        now = datetime.now()
        
        # 很新的消息
        recent_msg = Message(role="user", content="Recent", timestamp=now - timedelta(hours=1))
        recent_score = self.retriever._calculate_recency_score(recent_msg)
        
        # 较老的消息
        old_msg = Message(role="user", content="Old", timestamp=now - timedelta(hours=12))
        old_score = self.retriever._calculate_recency_score(old_msg)
        
        # 很老的消息
        very_old_msg = Message(role="user", content="Very old", timestamp=now - timedelta(hours=23))
        very_old_score = self.retriever._calculate_recency_score(very_old_msg)
        
        # 新消息应该有更高分数
        self.assertGreater(recent_score, old_score)
        self.assertGreater(old_score, very_old_score)
        
        # 没有时间戳的消息分数为0
        no_timestamp_msg = Message(role="user", content="No timestamp")
        no_timestamp_score = self.retriever._calculate_recency_score(no_timestamp_msg)
        self.assertEqual(no_timestamp_score, 0)


class TestCreateRetriever(unittest.TestCase):
    """检索器工厂函数测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_embedding_model = Mock()
    
    def test_create_semantic_retriever(self):
        """测试创建语义检索器"""
        config = RetrievalConfig(strategy=RetrievalStrategy.SEMANTIC)
        retriever = create_retriever(config, self.mock_embedding_model)
        self.assertIsInstance(retriever, SemanticRetriever)
    
    def test_create_keyword_retriever(self):
        """测试创建关键词检索器"""
        config = RetrievalConfig(strategy=RetrievalStrategy.KEYWORD)
        retriever = create_retriever(config, None)
        self.assertIsInstance(retriever, KeywordRetriever)
    
    def test_create_hybrid_retriever(self):
        """测试创建混合检索器"""
        config = RetrievalConfig(strategy=RetrievalStrategy.HYBRID)
        retriever = create_retriever(config, self.mock_embedding_model)
        self.assertIsInstance(retriever, HybridRetriever)
    
    def test_create_time_based_retriever(self):
        """测试创建时间检索器"""
        config = RetrievalConfig(strategy=RetrievalStrategy.TIME_BASED)
        retriever = create_retriever(config, None)
        self.assertIsInstance(retriever, TimeBasedRetriever)
    
    def test_create_semantic_without_embedding_model(self):
        """测试创建语义检索器但没有嵌入模型"""
        config = RetrievalConfig(strategy=RetrievalStrategy.SEMANTIC)
        with self.assertRaises(ValueError) as context:
            create_retriever(config, None)
        self.assertIn("嵌入模型", str(context.exception))
    
    def test_create_hybrid_without_embedding_model(self):
        """测试创建混合检索器但没有嵌入模型"""
        config = RetrievalConfig(strategy=RetrievalStrategy.HYBRID)
        with self.assertRaises(ValueError) as context:
            create_retriever(config, None)
        self.assertIn("嵌入模型", str(context.exception))
    
    def test_create_unsupported_strategy(self):
        """测试创建不支持的策略"""
        config = Mock()
        config.strategy = "unsupported_strategy"
        
        with self.assertRaises(ValueError) as context:
            create_retriever(config, self.mock_embedding_model)
        self.assertIn("不支持的检索策略", str(context.exception))


if __name__ == '__main__':
    unittest.main()