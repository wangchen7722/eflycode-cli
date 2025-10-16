from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field
from enum import Enum
import tomllib

from eflycode.constant import (
    EFLYCODE_USER_HOME_DIR,
    EFLYCODE_USER_CONFIG_FILE,
    EFLYCODE_PROJECT_HOME_DIR,
    EFLYCODE_PROJECT_CONFIG_FILE,
)
from eflycode.schema.config import LoggingConfig, ModelConfig, ModelEntry
from eflycode.schema.llm import LLMConfig
from eflycode.util.logger import configure_logging


class GlobalConfig:
    """全局配置管理器"""

    _instance: Optional["GlobalConfig"] = None
    _initialized: bool = False
    _vector_db_config: Optional["VectorDBConfig"] = None
    _logging_config: Optional[LoggingConfig] = None
    _model_config: Optional[ModelConfig] = None

    def __new__(cls) -> "GlobalConfig":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    @classmethod
    def get_instance(cls) -> "GlobalConfig":
        """获取全局配置实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_model_config(self) -> ModelConfig:
        """获取模型配置"""
        if self._model_config is None:
            raise ValueError("Model config not initialized")
        return self._model_config

    def get_default_llm_config(self) -> LLMConfig:
        """获取默认的LLM配置"""
        if self._model_config is None:
            raise ValueError("Model config not initialized")
        default_model = self._model_config.default
        if default_model is None:
            raise ValueError("Default model not specified in model config")
        for entry in self._model_config.entries:
            if entry.model == default_model:
                return LLMConfig(**entry.model_dump())
        raise ValueError(f"Default model {default_model} not found in model config")


    def _initialize(self) -> None:
        """初始化配置"""
        if self._initialized:
            return
        # 读取配置
        config = self._load_config()
        self._logging_config = self._parse_logging_config(config)
        # 配置日志记录器
        configure_logging(self._logging_config)
        self._model_config = self._parse_model_config(config)

    def _parse_logging_config(self, config: Dict[str, Any]) -> LoggingConfig:
        """解析日志配置"""
        logging_config = config.get("logging", {})
        return LoggingConfig(**logging_config)

    def _parse_model_config(self, config: Dict[str, Any]) -> ModelConfig:
        """解析模型配置"""
        model_config = config.get("model", {})
        return ModelConfig(
            default=model_config.get("default", None),
            entries=[ModelEntry(**entry) for entry in model_config.get("entries", [])],
        )

    def _load_config(self) -> Dict[str, Any]:
        # 加载用户目录配置和项目级配置，其中项目级配置优先级更高
        user_config = self._load_user_config()
        project_config = self._load_project_config()
        # 合并配置
        merged_config = self._deep_merge_config(user_config, project_config)
        return merged_config

    def _deep_merge_config(
        self, base: Dict[str, Any], overrides: Dict[str, Any]
    ) -> Dict[str, Any]:
        """合并用户配置和项目配置"""
        if base is None:
            return overrides
        if overrides is None:
            return base
        for key, value in overrides.items():
            if key in base:
                if isinstance(value, dict) and isinstance(base[key], dict):
                    base[key] = self._deep_merge_config(base[key], value)
                else:
                    base[key] = value
            else:
                base[key] = value
        return base

    def _load_user_config(self) -> None | Dict[str, Any]:
        """加载用户目录配置"""
        user_dir = EFLYCODE_USER_HOME_DIR
        user_dir.mkdir(parents=True, exist_ok=True)
        # 加载配置文件
        config_file = EFLYCODE_USER_CONFIG_FILE
        if config_file.exists():
            with open(config_file, "rb") as f:
                config_data = tomllib.load(f)
            return config_data
        else:
            # 创建空配置文件
            config_file.touch()
        return None

    def _load_project_config(self) -> None | Dict[str, Any]:
        """加载项目目录配置"""
        project_dir = EFLYCODE_PROJECT_HOME_DIR
        project_dir.mkdir(parents=True, exist_ok=True)
        # 加载配置文件
        config_file = EFLYCODE_PROJECT_CONFIG_FILE
        if config_file.exists():
            with open(config_file, "rb") as f:
                config_data = tomllib.load(f)
            return config_data
        else:
            # 创建空配置文件
            config_file.touch()
        return None


def get_global_config() -> GlobalConfig:
    """获取全局配置实例的便捷函数"""
    return GlobalConfig.get_instance()


class VectorDBConfig(BaseModel):
    """向量数据库配置"""

    vector_db_path: str = Field(
        default="./data/vector_db", description="向量数据库路径"
    )
    embedding_model: Optional[str] = Field(default=None, description="嵌入模型名称")
    short_term_capacity: int = Field(default=10, description="短期记忆容量")


# ==================== Agent配置相关 ====================


class MemoryType(Enum):
    """记忆类型枚举"""

    SHORT_TERM = "short_term"
    """短期记忆：在当前对话有用的临时信息"""

    LONG_TERM = "long_term"
    """长期记忆：存储重要的持久化信息，可长期保存，用于积累知识和经验"""

    WORKING = "working"
    """工作记忆：存储当前任务相关的活跃信息，容量有限但访问速度快"""

    EPISODIC = "episodic"
    """情节记忆：存储特定事件、对话和经历的详细上下文信息"""

    SEMANTIC = "semantic"
    """语义记忆：存储抽象概念、知识结构和事实性信息，支持推理和理解"""


class MemoryImportance(Enum):
    """记忆重要性枚举"""

    # 关键
    CRITICAL = 5
    # 高
    HIGH = 4
    # 中等
    MEDIUM = 3
    # 低
    LOW = 2
    # 最低
    MINIMAL = 1


class CompressionStrategy(Enum):
    """压缩策略枚举"""

    # 摘要压缩
    SUMMARY = "summary"
    # 关键信息提取
    KEY_EXTRACTION = "key_extraction"
    # 滑动窗口
    SLIDING_WINDOW = "sliding_window"
    # 压缩器链
    CHAIN = "chain"


class TokenCalculationStrategy(Enum):
    """Token计算策略枚举"""

    # 估算策略
    ESTIMATE = "estimate"
    """估算策略：基于字符数的简单估算方法"""

    # Tokenizer策略
    TOKENIZER = "tokenizer"
    """Tokenizer策略：使用HuggingFace tokenizers直接计算token数"""


class RetrievalStrategy(Enum):
    """检索策略枚举"""

    # 语义相似度
    SEMANTIC = "semantic"
    # 关键词匹配
    KEYWORD = "keyword"
    # 时间相关
    TEMPORAL = "temporal"
    # 混合策略
    HYBRID = "hybrid"
    # 相关性评分
    RELEVANCE = "relevance"
    

class MemoryType(Enum):
    """记忆类型"""

    WINDOW = "window"
    """滑动窗口记忆：存储所有消息，但每次读取时只返回最近 k 条"""
    
class SlidingWindowConfig(BaseModel):
    """滑动窗口记忆配置"""

    window_size: int = Field(
        default=5, description="滑动窗口大小，控制每次读取的消息数量"
    )


class MemoryConfig(BaseModel):
    """记忆管理配置"""
    
    type: MemoryType
    short_term_capacity: int = Field(
        default=50, description="短期记忆容量限制，控制可存储的短期记忆数量"
    )
    working_memory_capacity: int = Field(
        default=10, description="工作记忆容量限制，控制当前活跃的工作记忆数量"
    )
    long_term_capacity: int = Field(
        default=1000, description="长期记忆容量限制，控制可存储的长期记忆数量"
    )
    short_term_ttl_hours: int = Field(
        default=24, description="短期记忆生存时间（小时），超过此时间的短期记忆将被清理"
    )
    working_memory_ttl_minutes: int = Field(
        default=30, description="工作记忆生存时间（分钟），超过此时间的工作记忆将被清理"
    )

    long_term_importance_threshold: MemoryImportance = Field(
        default=MemoryImportance.MEDIUM,
        description="长期记忆重要性阈值，只有达到此重要性级别的记忆才会被转为长期记忆",
    )
    enable_forgetting: bool = Field(
        default=True, description="是否启用遗忘机制，控制记忆是否会随时间衰减"
    )
    forgetting_curve_factor: float = Field(
        default=0.1, description="遗忘曲线因子，控制记忆衰减的速度，值越大衰减越快"
    )
    min_access_for_retention: int = Field(
        default=2,
        description="保留记忆的最小访问次数，访问次数低于此值的记忆更容易被遗忘",
    )
    storage_path: str = Field(
        default="./memory_storage", description="记忆存储路径，用于持久化存储记忆数据"
    )
    enable_persistence: bool = Field(
        default=True, description="是否启用持久化存储，控制记忆是否保存到磁盘"
    )
    similarity_threshold: float = Field(
        default=0.7, description="相似度阈值，用于记忆检索时的相似度匹配"
    )
    max_retrieval_results: int = Field(
        default=10, description="最大检索结果数量，限制单次记忆检索返回的结果数量"
    )


class CompressionConfig(BaseModel):
    """上下文压缩配置"""

    strategy: CompressionStrategy = Field(
        default=CompressionStrategy.CHAIN,
        description="压缩策略，决定使用哪种方式压缩对话历史",
    )
    compression_ratio: float = Field(
        default=0.3, description="压缩比例，目标压缩后内容与原内容的比例"
    )
    preserve_recent_messages: int = Field(
        default=5, description="保留最近消息数量，最新的N条消息将被完整保留不压缩"
    )

    # 基于上下文长度的压缩触发配置
    max_context_length: int = Field(
        default=32000, description="模型支持的最大上下文长度"
    )
    context_usage_threshold: float = Field(
        default=0.8,
        description="上下文使用阈值，当当前上下文长度超过最大上下文长度的此比例时触发压缩",
    )
    target_context_length_ratio: float = Field(
        default=0.6,
        description="目标上下文长度比例，压缩后的上下文长度应为最大上下文长度的此比例",
    )

    summary_max_tokens: int = Field(
        default=500, description="摘要最大token数量，使用摘要压缩时生成摘要的最大长度"
    )

    # 压缩器链配置
    chain_compressor_types: List[str] = Field(
        default=["key_extraction", "sliding_window"],
        description="压缩器链中使用的压缩器类型列表",
    )
    chain_selection_strategy: str = Field(
        default="best_ratio",
        description="压缩器链的结果选择策略：best_ratio, best_score, most_messages",
    )

    # Token计算相关配置
    token_calculation_strategy: TokenCalculationStrategy = Field(
        default=TokenCalculationStrategy.ESTIMATE,
        description="Token计算策略，决定使用哪种方式计算token数量",
    )
    api_base_url: Optional[str] = Field(
        default=None, description="Token计算API的基础URL，使用API策略时需要"
    )
    api_key: Optional[str] = Field(
        default=None, description="Token计算API的密钥，使用API策略时需要"
    )
    model_name: str = Field(
        default="gpt-3.5-turbo",
        description="模型名称，用于API和Transformers策略的token计算",
    )
    tokenizer_cache_dir: Optional[str] = Field(
        default=None, description="Tokenizer缓存目录，使用Transformers策略时的缓存路径"
    )

    @property
    def compression_trigger_length(self) -> int:
        """计算触发压缩的上下文长度阈值"""
        return int(self.max_context_length * self.context_usage_threshold)

    @property
    def target_context_length(self) -> int:
        """计算压缩后的目标上下文长度"""
        return int(self.max_context_length * self.target_context_length_ratio)


class RetrievalConfig(BaseModel):
    """上下文检索配置"""

    strategy: RetrievalStrategy = Field(
        default=RetrievalStrategy.HYBRID,
        description="检索策略，决定使用哪种方式检索相关上下文",
    )
    max_results: int = Field(
        default=10, description="最大检索结果数量，单次检索返回的最大结果数"
    )
    similarity_threshold: float = Field(
        default=0.7, description="相似度阈值，只有相似度超过此值的内容才会被检索"
    )
    time_window_hours: int = Field(
        default=24, description="时间窗口（小时），限制检索内容的时间范围"
    )
    keyword_weight: float = Field(
        default=0.3, description="关键词权重，在混合检索策略中关键词匹配的权重"
    )

    semantic_weight: float = Field(
        default=0.5, description="语义权重，在混合检索策略中语义相似度的权重"
    )
    temporal_weight: float = Field(
        default=0.2, description="时间权重，在混合检索策略中时间相关性的权重"
    )
    min_content_length: int = Field(
        default=10, description="最小内容长度，内容长度小于此值的消息将被过滤"
    )
    enable_fuzzy_match: bool = Field(
        default=True, description="是否启用模糊匹配，允许部分匹配的关键词检索"
    )
