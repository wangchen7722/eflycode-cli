import os
import fnmatch
from typing import Optional, List
from pathlib import Path
from pydantic import BaseModel, Field


class IgnoreManager:
    """文件忽略管理器"""
    
    def __init__(self, ignore_config: 'EchoIgnoreConfig'):
        self.ignore_config = ignore_config
    
    def load_ignore_patterns(self, base_path: str = ".") -> List[str]:
        """加载忽略模式
        
        Args:
            base_path: 基础路径，用于查找.echoignore文件
            
        Returns:
            忽略模式列表
        """
        patterns = self.ignore_config.default_patterns.copy()
        
        # 查找.echoignore文件
        ignore_file_path = Path(base_path) / self.ignore_config.ignore_file_name
        
        if ignore_file_path.exists() and ignore_file_path.is_file():
            try:
                with open(ignore_file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        # 跳过空行和注释行
                        if line and not line.startswith('#'):
                            patterns.append(line)
            except Exception as e:
                # 如果读取失败，只使用默认模式
                print(f"警告：无法读取.echoignore文件: {e}")
        
        return patterns
    
    def should_ignore(self, file_path: str, patterns: List[str]) -> bool:
        """检查文件是否应该被忽略
        
        Args:
            file_path: 文件路径
            patterns: 忽略模式列表
            
        Returns:
            是否应该忽略该文件
        """
        path_obj = Path(file_path)
        
        # 检查文件名和路径的各个部分
        for pattern in patterns:
            # 去除模式末尾的斜杠（用于目录匹配）
            clean_pattern = pattern.rstrip('/')
            
            # 检查完整路径
            if fnmatch.fnmatch(str(path_obj), pattern) or fnmatch.fnmatch(str(path_obj), clean_pattern):
                return True
            
            # 检查文件名
            if fnmatch.fnmatch(path_obj.name, pattern) or fnmatch.fnmatch(path_obj.name, clean_pattern):
                return True
            
            # 检查路径中的任何部分
            for part in path_obj.parts:
                if fnmatch.fnmatch(part, pattern) or fnmatch.fnmatch(part, clean_pattern):
                    return True
                    
            # 特殊处理目录模式（以/结尾）
            if pattern.endswith('/') and path_obj.is_dir():
                if fnmatch.fnmatch(path_obj.name, clean_pattern):
                    return True
        
        return False


class VectorDBConfig(BaseModel):
    """向量数据库配置"""
    
    vector_db_path: str = Field(default="./data/vector_db", description="向量数据库路径")
    embedding_model: Optional[str] = Field(default=None, description="嵌入模型名称")
    short_term_capacity: int = Field(default=10, description="短期记忆容量")


class EchoIgnoreConfig(BaseModel):
    """Echo忽略文件配置"""
    
    ignore_file_name: str = Field(default=".echoignore", description="忽略文件名称")
    default_patterns: List[str] = Field(
        default_factory=lambda: [
            "__pycache__",
            "node_modules",
        ],
        description="默认忽略模式"
    )


class GlobalConfig:
    """全局配置管理器"""
    
    _instance: Optional['GlobalConfig'] = None
    _vector_db_config: Optional[VectorDBConfig] = None
    _echo_ignore_config: Optional[EchoIgnoreConfig] = None
    
    def __new__(cls) -> 'GlobalConfig':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> 'GlobalConfig':
        """获取全局配置实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @property
    def vector_db_config(self) -> VectorDBConfig:
        """获取向量数据库配置"""
        if self._vector_db_config is None:
            self._vector_db_config = self._load_vector_db_config()
        return self._vector_db_config
    
    @property
    def echo_ignore_config(self) -> EchoIgnoreConfig:
        """获取Echo忽略文件配置"""
        if self._echo_ignore_config is None:
            self._echo_ignore_config = EchoIgnoreConfig()
        return self._echo_ignore_config
    
    def _load_vector_db_config(self) -> VectorDBConfig:
        """从环境变量或配置文件加载向量数据库配置"""
        return VectorDBConfig(
            vector_db_path=os.getenv("ECHO_VECTOR_DB_PATH", "./data/vector_db"),
            embedding_model=os.getenv("ECHO_EMBEDDING_MODEL"),
            short_term_capacity=int(os.getenv("ECHO_SHORT_TERM_CAPACITY", "10"))
        )
    
    def update_vector_db_config(self, config: VectorDBConfig) -> None:
        """更新向量数据库配置"""
        self._vector_db_config = config
    
    def update_echo_ignore_config(self, config: EchoIgnoreConfig) -> None:
        """更新Echo忽略文件配置"""
        self._echo_ignore_config = config
    
    def get_ignore_manager(self) -> IgnoreManager:
        """获取文件忽略管理器实例"""
        return IgnoreManager(self.echo_ignore_config)


def get_global_config() -> GlobalConfig:
    """获取全局配置实例的便捷函数"""
    return GlobalConfig.get_instance()