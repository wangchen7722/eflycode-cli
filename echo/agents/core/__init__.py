"""AI代理核心模块

提供AI代理的核心功能，包括：
- Token计算器
- 上下文管理（压缩和检索）
- 记忆管理
"""

# Token计算
from .token_calculator import (
    TokenCalculator,
    EstimateTokenCalculator,
    APITokenCalculator,
    TransformersTokenCalculator,
    create_token_calculator
)

# 上下文管理
from .context import (
    # 压缩器
    BaseCompressor,
    CompressionResult,
    SummaryCompressor,
    SlidingWindowCompressor,
    KeyExtractionCompressor,
    HybridCompressor,
    create_compressor,
    
    # 检索器
    BaseRetriever,
    RetrievalResult,
    ContextEntry,
    KeywordRetriever,
    SemanticRetriever,
    TemporalRetriever,
    HybridRetriever,
    RetrievalStrategy,
    create_retriever,
    ContextRetriever
)

# 记忆管理
from .memory import (
    MemoryItem,
    BaseMemoryStore,
    InMemoryStore,
    SQLiteMemoryStore,
    MemoryManager
)

__all__ = [
    # Token计算
    'TokenCalculator',
    'EstimateTokenCalculator',
    'APITokenCalculator',
    'TransformersTokenCalculator',
    'create_token_calculator',
    
    # 上下文压缩
    'BaseCompressor',
    'CompressionResult',
    'SummaryCompressor',
    'SlidingWindowCompressor',
    'KeyExtractionCompressor',
    'HybridCompressor',
    'create_compressor',
    
    # 上下文检索
    'BaseRetriever',
    'RetrievalResult',
    'ContextEntry',
    'KeywordRetriever',
    'SemanticRetriever',
    'TemporalRetriever',
    'HybridRetriever',
    'RetrievalStrategy',
    'create_retriever',
    'ContextRetriever',
    
    # 记忆管理
    'MemoryItem',
    'BaseMemoryStore',
    'InMemoryStore',
    'SQLiteMemoryStore',
    'MemoryManager',
]