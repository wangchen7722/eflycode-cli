from typing import Dict, List, Optional, Any, Union, ClassVar, Sequence
import time
import json
import os

import chromadb
from chromadb.utils.embedding_functions.sentence_transformer_embedding_function import \
    SentenceTransformerEmbeddingFunction

from echo.memory.schema import MemoryItem, MemoryType


class GlobalMemory:
    """全局记忆管理类，实现跨会话或跨智能体的共享记忆
    
    该类使用单例模式，确保在整个应用程序中只有一个实例
    """

    _instance: ClassVar[Optional["GlobalMemory"]] = None

    def __new__(cls, *args, **kwargs):
        """实现单例模式"""
        if cls._instance is None:
            cls._instance = super(GlobalMemory, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
            self,
            vector_db_path: Optional[str] = None,
            embedding_model: Optional[str] = None,
            capacity: int = 100,
    ):
        """初始化全局记忆管理器
        
        Args:
            capacity: 全局记忆容量
            embedding_model: 嵌入模型名称
            vector_db_path: 向量数据库保存路径
        """
        # 避免重复初始化
        if getattr(self, "_initialized", False):
            return

        if vector_db_path is None:
            vector_db_path = "::memory::"
        if embedding_model is None:
            embedding_model = "all-MiniLM-L6-v2"

        self.capacity = capacity
        self.global_memory: List[MemoryItem] = []

        # 向量数据库相关初始化
        self.vector_db_path = vector_db_path
        self.embedding_model_name = embedding_model

        # 初始化向量数据库和嵌入模型
        self.embedding_function = SentenceTransformerEmbeddingFunction(model_name=self.embedding_model_name)
        # 如果提供了路径，使用持久化存储，否则使用内存存储
        if self.vector_db_path == "::memory::":
            self.chroma_client = chromadb.EphemeralClient()
        else:
            os.makedirs(os.path.dirname(self.vector_db_path), exist_ok=True)
            self.chroma_client = chromadb.PersistentClient(path=self.vector_db_path)

        # 创建或获取集合
        self.global_collection = self.chroma_client.get_or_create_collection(
            name="global_memory",
            metadata={"hnsw:space": "cosine"}
        )

        # 加载记忆项元数据
        if self.vector_db_path:
            self._load_memory_metadata()

        self._initialized = True

    def _load_memory_metadata(self):
        """加载记忆项元数据"""
        metadata_path = os.path.join(self.vector_db_path, "global_memory_metadata.json")
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    memory_data = json.load(f)

                    # 加载全局记忆
                    for item in memory_data.get("global", []):
                        self.global_memory.append(MemoryItem.from_dict(item))
            except Exception as e:
                print(f"加载全局记忆元数据失败: {e}")

    def _get_embedding(self, text: str) -> Optional[Union[Sequence[float], Sequence[int]]]:
        """获取文本的向量嵌入
        
        Args:
            text: 输入文本
            
        Returns:
            Optional[np.ndarray]: 向量嵌入，如果失败则返回None
        """
        if not self.embedding_function:
            return None

        try:
            return self.embedding_function([text])[0].tolist()
        except Exception as e:
            print(f"获取文本嵌入失败: {e}")
            return None

    def add_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> MemoryItem:
        """添加全局记忆
        
        Args:
            content: 记忆内容
            metadata: 元数据
            
        Returns:
            MemoryItem: 创建的记忆项
        """
        metadata = metadata or {}

        # 生成唯一ID
        item_id = f"global_{int(time.time())}_{hash(content) % 10000}"

        # 创建记忆项 - 全局记忆使用LONG_TERM类型
        memory_item = MemoryItem(
            id=item_id,
            content=content,
            type=MemoryType.LONG_TERM,
            metadata=metadata,
            embedding=None
        )

        # 获取向量嵌入
        if self.embedding_function:
            embedding_np = self._get_embedding(content)
            if embedding_np is not None:
                memory_item.embedding = embedding_np

        if memory_item.embedding:
            # 添加到向量数据库
            chroma_metadata = {**metadata, "timestamp": memory_item.timestamp}
            self.global_collection.add(
                ids=[item_id],
                embeddings=[memory_item.embedding],
                documents=[content],
                metadatas=[chroma_metadata]
            )

        # 添加到全局记忆
        self.global_memory.append(memory_item)

        # 如果全局记忆超出容量，移除最旧的记忆
        if len(self.global_memory) > self.capacity:
            oldest_item = self.global_memory.pop(0)
            # 从ChromaDB中删除
            try:
                self.global_collection.delete(ids=[oldest_item.id])
            except Exception as e:
                print(f"从ChromaDB删除全局记忆失败: {e}")

        return memory_item

    def search_memory(self, query: str, top_k: int = 5) -> List[MemoryItem]:
        """搜索相关全局记忆
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            
        Returns:
            List[MemoryItem]: 相关记忆列表
        """
        results = []
        query_embedding = self._get_embedding(query)

        if query_embedding is None:
            # 如果embedding_function不可用，返回最近的记忆
            results.extend(self.global_memory)
            # 按时间戳排序，最新的在前
            results.sort(key=lambda x: x.timestamp, reverse=True)
            return results[:top_k]

        # 使用ChromaDB搜索
        try:
            # 从全局记忆搜索
            global_results = []
            if self.global_collection:
                results_global = self.global_collection.query(
                    query_embeddings=query_embedding,
                    n_results=top_k
                )

                if results_global and results_global["ids"] and results_global["ids"][0]:
                    for i, item_id in enumerate(results_global["ids"][0]):
                        # 查找对应的记忆项
                        for memory_item in self.global_memory:
                            if memory_item.id == item_id:
                                global_results.append(memory_item)
                                break

            return global_results
        except Exception as e:
            print(f"搜索全局记忆失败: {e}")
            # 发生异常时，返回最近的记忆
            results.extend(self.global_memory)
            # 按时间戳排序，最新的在前
            results.sort(key=lambda x: x.timestamp, reverse=True)
            return results[:top_k]

    def save_memory(self) -> bool:
        """保存全局记忆到磁盘
        
        Returns:
            bool: 是否成功保存
        """

        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.vector_db_path), exist_ok=True)

            # 保存记忆元数据
            metadata_path = os.path.join(self.vector_db_path, "global_memory_metadata.json")
            memory_data = {
                "global": [item.to_dict() for item in self.global_memory],
            }

            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(memory_data, f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            print(f"保存全局记忆失败: {e}")
            return False

    def clear_memory(self) -> bool:
        """清除全局记忆
        
        Returns:
            bool: 是否成功清除
        """
        try:
            try:
                # 获取所有ID
                ids = [item.id for item in self.global_memory if item.id]
                if ids:
                    self.global_collection.delete(ids=ids)
            except Exception as e:
                print(f"清除全局记忆集合失败: {e}")
            self.global_memory = []

            if self.vector_db_path:
                self.save_memory()

            return True
        except Exception as e:
            print(f"清除全局记忆失败: {e}")
            return False

    def get_memory_by_id(self, memory_id: str) -> Optional[MemoryItem]:
        """根据ID获取全局记忆项
        
        Args:
            memory_id: 记忆项ID
            
        Returns:
            Optional[MemoryItem]: 记忆项，如果未找到则返回None
        """
        # 在全局记忆中查找
        for item in self.global_memory:
            if item.id == memory_id:
                return item

        return None

    def get_recent_memories(self, limit: int = 5) -> List[MemoryItem]:
        """获取最近的全局记忆
        
        Args:
            limit: 返回结果数量
            
        Returns:
            List[MemoryItem]: 最近的记忆列表
        """
        results = self.global_memory.copy()

        # 按时间戳排序，最新的在前
        results.sort(key=lambda x: x.timestamp, reverse=True)

        return results[:limit]

    @classmethod
    def get_instance(cls) -> "GlobalMemory":
        """获取GlobalMemory的单例实例
        
        如果实例尚未初始化，将抛出异常
        
        Returns:
            GlobalMemory: 全局记忆管理器实例
        """
        if cls._instance is None or not getattr(cls._instance, "_initialized", False):
            raise RuntimeError("GlobalMemory尚未初始化，请先调用构造函数")
        return cls._instance
