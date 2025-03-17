from typing import Dict, List, Optional, Any, Union
from enum import Enum
import time
import json
import os
from pydantic import BaseModel, Field

import numpy as np
from numpy.typing import NDArray
import chromadb
from chromadb.utils.embedding_functions.sentence_transformer_embedding_function import SentenceTransformerEmbeddingFunction

class MemoryType(Enum):
    """记忆类型枚举"""
    SHORT_TERM = "short_term"  # 短期记忆
    LONG_TERM = "long_term"    # 长期记忆

class MemoryItem(BaseModel):
    """记忆项模型"""
    id: str = Field(..., description="唯一标识符")
    content: str = Field(..., description="记忆内容")
    type: MemoryType = Field(..., description="记忆类型")
    timestamp: float = Field(default_factory=time.time, description="创建时间戳")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    embedding: Optional[NDArray[Union[np.int32, np.float32]]] = Field(None, description="向量嵌入")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "content": self.content,
            "type": self.type.value,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        """从字典创建记忆项"""
        if "type" in data and isinstance(data["type"], str):
            data["type"] = MemoryType(data["type"])
        return cls(**data)

class Memory:
    """记忆管理类，实现分层记忆结构和向量检索"""
    
    def __init__(
        self,
        vector_db_path: str,
        short_term_capacity: int = 10,
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        """初始化记忆管理器
        
        Args:
            short_term_capacity: 短期记忆容量
            embedding_model: 嵌入模型名称
            vector_db_path: 向量数据库保存路径
        """
        self.short_term_capacity = short_term_capacity
        self.short_term_memory: List[MemoryItem] = []
        self.long_term_memory: List[MemoryItem] = []
        
        # 向量数据库相关初始化
        self.vector_db_path = vector_db_path
        self.embedding_model_name = embedding_model
        
        # 初始化向量数据库和嵌入模型
        self.embedding_function = SentenceTransformerEmbeddingFunction(model_name=self.embedding_model_name)
        # 如果提供了路径，使用持久化存储，否则使用内存存储
        os.makedirs(os.path.dirname(self.vector_db_path), exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=self.vector_db_path)
        
        # 创建或获取集合
        self.short_term_collection = self.chroma_client.get_or_create_collection(
            name="short_term_memory",
            metadata={"hnsw:space": "cosine"}
        )
        
        self.long_term_collection = self.chroma_client.get_or_create_collection(
            name="long_term_memory",
            metadata={"hnsw:space": "cosine"}
        )
        
        # 加载记忆项元数据
        if self.vector_db_path:
            self._load_memory_metadata()
    
    def _load_memory_metadata(self):
        """加载记忆项元数据"""
        metadata_path = os.path.join(self.vector_db_path, "memory_metadata.json")
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    memory_data = json.load(f)
                    
                    # 加载短期记忆
                    for item in memory_data.get("short_term", []):
                        self.short_term_memory.append(MemoryItem.from_dict(item))
                    
                    # 加载长期记忆
                    for item in memory_data.get("long_term", []):
                        self.long_term_memory.append(MemoryItem.from_dict(item))
            except Exception as e:
                print(f"加载记忆元数据失败: {e}")
    
    def _get_embedding(self, text: str) -> Optional[NDArray[Union[np.int32, np.float32]]]:
        """获取文本的向量嵌入
        
        Args:
            text: 输入文本
            
        Returns:
            Optional[np.ndarray]: 向量嵌入，如果失败则返回None
        """
        if not self.embedding_function:
            return None
        
        try:
            return self.embedding_function([text])[0]
        except Exception as e:
            print(f"获取文本嵌入失败: {e}")
            return None
    
    def add_memory(self, content: str, memory_type: MemoryType, metadata: Optional[Dict[str, Any]] = None) -> MemoryItem:
        """添加记忆
        
        Args:
            content: 记忆内容
            memory_type: 记忆类型
            metadata: 元数据
            
        Returns:
            MemoryItem: 创建的记忆项
        """
        metadata = metadata or {}
        
        # 生成唯一ID
        item_id = f"{int(time.time())}_{hash(content) % 10000}"
        
        # 创建记忆项
        memory_item = MemoryItem(
            id=item_id,
            content=content,
            type=memory_type,
            metadata=metadata,
            embedding=None
        )
        
        # 获取向量嵌入
        if self.embedding_function:
            embedding_np = self._get_embedding(content)
            if embedding_np is not None:
                memory_item.embedding = embedding_np
                
        if memory_item.embedding:
            # 根据记忆类型选择集合
            collection = self.short_term_collection if memory_type == MemoryType.SHORT_TERM else self.long_term_collection
            chroma_metadata = {**metadata, "timestamp": memory_item.timestamp}
            collection.add(
                ids=[item_id],
                embeddings=[memory_item.embedding],
                documents=[content],
                metadatas=[chroma_metadata]
            )
        
        # 根据记忆类型添加到不同的记忆存储
        if memory_type == MemoryType.SHORT_TERM:
            self.short_term_memory.append(memory_item)
            
            # 如果短期记忆超出容量，移除最旧的记忆
            if len(self.short_term_memory) > self.short_term_capacity:
                oldest_item = self.short_term_memory.pop(0)
                # 从ChromaDB中删除
                try:
                    self.short_term_collection.delete(ids=[oldest_item.id])
                except Exception as e:
                    print(f"从ChromaDB删除记忆失败: {e}")
                    
        else:  # 长期记忆
            self.long_term_memory.append(memory_item)
        
        return memory_item
    
    def search_memory(self, query: str, top_k: int = 5, include_short_term: bool = True, include_long_term: bool = True) -> List[MemoryItem]:
        """搜索相关记忆
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            include_short_term: 是否包含短期记忆
            include_long_term: 是否包含长期记忆
            
        Returns:
            List[MemoryItem]: 相关记忆列表
        """
        results = []
        query_embedding = self._get_embedding(query)
        
        if query_embedding is None:
            # 如果embedding_function不可用，返回最近的记忆
            if include_short_term:
                results.extend(self.short_term_memory)
            if include_long_term:
                results.extend(self.long_term_memory)
            # 按时间戳排序，最新的在前
            results.sort(key=lambda x: x.timestamp, reverse=True)
            return results[:top_k]
        
        # 使用ChromaDB搜索
        try:
            # 从短期记忆搜索
            short_term_results = []
            if include_short_term and self.short_term_collection:
                results_short = self.short_term_collection.query(
                    query_embeddings=query_embedding,
                    n_results=top_k
                )
                
                if results_short and results_short['ids'] and results_short['ids'][0]:
                    for i, item_id in enumerate(results_short['ids'][0]):
                        # 查找对应的记忆项
                        for memory_item in self.short_term_memory:
                            if memory_item.id == item_id:
                                short_term_results.append(memory_item)
                                break
            
            # 从长期记忆搜索
            long_term_results = []
            if include_long_term and self.long_term_collection:
                results_long = self.long_term_collection.query(
                    query_embeddings=query_embedding,
                    n_results=top_k
                )
                
                if results_long and results_long['ids'] and results_long['ids'][0]:
                    for i, item_id in enumerate(results_long['ids'][0]):
                        # 查找对应的记忆项
                        for memory_item in self.long_term_memory:
                            if memory_item.id == item_id:
                                long_term_results.append(memory_item)
                                break
            
            # 合并结果
            results = short_term_results + long_term_results
            
            # 如果结果数量超过top_k，按相关性排序并截取
            if len(results) > top_k:
                # 由于我们已经通过向量搜索获取了最相关的结果，这里直接截取
                results = results[:top_k]
                
            return results
        except Exception as e:
            print(f"搜索记忆失败: {e}")
            # 发生异常时，返回最近的记忆
            if include_short_term:
                results.extend(self.short_term_memory)
            if include_long_term:
                results.extend(self.long_term_memory)
            # 按时间戳排序，最新的在前
            results.sort(key=lambda x: x.timestamp, reverse=True)
            return results[:top_k]
    
    def save_memory(self) -> bool:
        """保存记忆到磁盘
        
        Returns:
            bool: 是否成功保存
        """
        
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.vector_db_path), exist_ok=True)
            
            # 保存记忆元数据
            metadata_path = os.path.join(self.vector_db_path, "memory_metadata.json")
            memory_data = {
                "short_term": [item.to_dict() for item in self.short_term_memory],
                "long_term": [item.to_dict() for item in self.long_term_memory]
            }
            
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(memory_data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"保存记忆失败: {e}")
            return False
    
    def clear_memory(self, memory_type: Optional[MemoryType] = None) -> bool:
        """清除记忆
        
        Args:
            memory_type: 要清除的记忆类型，如果为None则清除所有记忆
            
        Returns:
            bool: 是否成功清除
        """
        try:
            # 清除短期记忆
            if memory_type is None or memory_type == MemoryType.SHORT_TERM:
                try:
                    # 获取所有ID
                    ids = [item.id for item in self.short_term_memory if item.id]
                    if ids:
                        self.short_term_collection.delete(ids=ids)
                except Exception as e:
                    print(f"清除短期记忆集合失败: {e}")
                self.short_term_memory = []
            
            # 清除长期记忆
            if memory_type is None or memory_type == MemoryType.LONG_TERM:
                try:
                    # 获取所有ID
                    ids = [item.id for item in self.long_term_memory if item.id]
                    if ids:
                        self.long_term_collection.delete(ids=ids)
                except Exception as e:
                    print(f"清除长期记忆集合失败: {e}")
                self.long_term_memory = []
            
            if self.vector_db_path:
                self.save_memory()
            
            return True
        except Exception as e:
            print(f"清除记忆失败: {e}")
            return False
    
    def get_memory_by_id(self, memory_id: str) -> Optional[MemoryItem]:
        """根据ID获取记忆项
        
        Args:
            memory_id: 记忆项ID
            
        Returns:
            Optional[MemoryItem]: 记忆项，如果未找到则返回None
        """
        # 在短期记忆中查找
        for item in self.short_term_memory:
            if item.id == memory_id:
                return item
        
        # 在长期记忆中查找
        for item in self.long_term_memory:
            if item.id == memory_id:
                return item
        
        return None
    
    def get_recent_memories(self, limit: int = 5, memory_type: Optional[MemoryType] = None) -> List[MemoryItem]:
        """获取最近的记忆
        
        Args:
            limit: 返回结果数量
            memory_type: 记忆类型，如果为None则返回所有类型
            
        Returns:
            List[MemoryItem]: 最近的记忆列表
        """
        results = []
        
        # 根据记忆类型筛选
        if memory_type is None or memory_type == MemoryType.SHORT_TERM:
            results.extend(self.short_term_memory)
        
        if memory_type is None or memory_type == MemoryType.LONG_TERM:
            results.extend(self.long_term_memory)
        
        # 按时间戳排序，最新的在前
        results.sort(key=lambda x: x.timestamp, reverse=True)
        
        return results[:limit]