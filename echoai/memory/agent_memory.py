from typing import Dict, List, Optional, Any, Sequence
import time
import json
import os

from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_chroma.vectorstores import Chroma
from langchain_community.docstore.document import Document

from echoai.memory.schema import MemoryItem, MemoryType


class AgentMemory:
    """记忆管理类，实现分层记忆结构和向量检索"""

    def __init__(
        self,
        vector_db_path: Optional[str] = None,
        embedding_model: Optional[str] = None,
        short_term_capacity: int = 10,
    ):
        """初始化记忆管理器
        
        Args:
            short_term_capacity: 短期记忆容量
            embedding_model: 嵌入模型名称
            vector_db_path: 向量数据库保存路径
        """
        if vector_db_path is None:
            vector_db_path = "::memory::"
        if embedding_model is None:
            embedding_model = "all-MiniLM-L6-v2"
            
        self.short_term_capacity = short_term_capacity
        self.short_term_memory: List[MemoryItem] = []
        self.long_term_memory: List[MemoryItem] = []

        self.vector_db_path = vector_db_path
        self.embedding_model_name = embedding_model

        # 初始化 Langchain SentenceTransformer embeddings
        self.embedding_function = HuggingFaceEmbeddings(
            model_name=self.embedding_model_name
        )

        # 初始化 Langchain Chroma 存储
        self.short_term_collection = Chroma(
            collection_name="short_term_memory",
            embedding_function=self.embedding_function,
            persist_directory=self.vector_db_path if self.vector_db_path != "::memory::" else None
        )

        self.long_term_collection = Chroma(
            collection_name="long_term_memory",
            embedding_function=self.embedding_function,
            persist_directory=self.vector_db_path if self.vector_db_path != "::memory::" else None
        )

        # 加载记忆项元数据
        if self.vector_db_path:
            self._load_memory_metadata()
    
    def is_empty(self) -> bool:
        """检查记忆是否为空"""
        return not (self.short_term_memory or self.long_term_memory)

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

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """获取文本的向量嵌入
        
        Args:
            text: 输入文本
            
        Returns:
            Optional[np.ndarray]: 向量嵌入，如果失败则返回None
        """
        try:
            return self.embedding_function.embed_query(text)
        except Exception as e:
            print(f"获取文本嵌入失败: {e}")
            return None

    def store_memory(self, content: str, memory_type: MemoryType,
                   metadata: Optional[Dict[str, Any]] = None) -> MemoryItem:
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

        # 创建 Langchain Document
        doc = Document(
            page_content=content,
            metadata={**metadata, "timestamp": memory_item.timestamp, "id": item_id}
        )

        # 存储到向量数据库
        collection = self.short_term_collection if memory_type == MemoryType.SHORT_TERM else self.long_term_collection
        collection.add_documents([doc])

        if memory_type == MemoryType.SHORT_TERM:
            self.short_term_memory.append(memory_item)

            # 如果短期记忆超出容量，移除最旧的记忆
            if len(self.short_term_memory) > self.short_term_capacity:
                oldest_item = self.short_term_memory.pop(0)
                # 从向量存储中删除
                try:
                    self.short_term_collection.delete([oldest_item.id])
                except Exception as e:
                    print(f"从向量存储删除记忆失败: {e}")

        else:  # 长期记忆
            self.long_term_memory.append(memory_item)

        return memory_item

    def search_memory(self, query: str, top_k: int = 5, include: Sequence[MemoryType] = (
            MemoryType.SHORT_TERM,
            MemoryType.LONG_TERM
    )) -> List[MemoryItem]:
        """搜索相关记忆
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            include: 记忆类型

        Returns:
            List[MemoryItem]: 相关记忆列表
        """

        include_short_term = MemoryType.SHORT_TERM in include
        include_long_term = MemoryType.LONG_TERM in include
        results = []

        try:
            # 使用 Langchain 搜索
            if include_short_term:
                docs = self.short_term_collection.similarity_search(query, k=top_k)
                for doc in docs:
                    item_id = doc.metadata.get("id")
                    for memory_item in self.short_term_memory:
                        if memory_item.id == item_id:
                            results.append(memory_item)
                            break

            if include_long_term:
                docs = self.long_term_collection.similarity_search(query, k=top_k)
                for doc in docs:
                    item_id = doc.metadata.get("id")
                    for memory_item in self.long_term_memory:
                        if memory_item.id == item_id:
                            results.append(memory_item)
                            break

            return results[:top_k]
        except Exception as e:
            print(f"搜索记忆失败: {e}")
            # 发生异常时，返回最近的记忆
            return self.get_recent_memories(limit=top_k, include=include)

    def save_memory(self) -> bool:
        """保存记忆到磁盘
        
        Returns:
            bool: 是否成功保存
        """
        if self.vector_db_path == "::memory::":
            # 如果是内存存储，不保存
            return True
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
                self.short_term_collection = Chroma(
                    collection_name="short_term_memory",
                    embedding_function=self.embedding_function,
                    persist_directory=self.vector_db_path if self.vector_db_path != "::memory::" else None
                )
                self.short_term_memory = []

            # 清除长期记忆
            if memory_type is None or memory_type == MemoryType.LONG_TERM:
                self.long_term_collection = Chroma(
                    collection_name="long_term_memory",
                    embedding_function=self.embedding_function,
                    persist_directory=self.vector_db_path if self.vector_db_path != "::memory::" else None
                )
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

    def get_recent_memories(self, limit: int = 5, include: Sequence[MemoryType] = [
        MemoryType.SHORT_TERM,
        MemoryType.LONG_TERM
    ]) -> List[MemoryItem]:
        """获取最近的记忆
        
        Args:
            limit: 返回结果数量
            include: 记忆类型
            
        Returns:
            List[MemoryItem]: 最近的记忆列表
        """
        results = []
        include_short_term = MemoryType.SHORT_TERM in include
        include_long_term = MemoryType.LONG_TERM in include

        # 根据记忆类型筛选
        if include_short_term:
            results.extend(self.short_term_memory)

        if include_long_term:
            results.extend(self.long_term_memory)

        # 按时间戳排序，最新的在前
        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results[:limit]


if __name__ == "__main__":
    memory = AgentMemory()
    memory.store_memory("用户向AI助手问候，询问其状态。助手解释其作为AI没有情感，但愿意提供帮助。", MemoryType.SHORT_TERM)
    memory.store_memory(content="用户计划欧洲旅行，寻求建议。助手询问用户感兴趣的国家、城市或活动。", memory_type=MemoryType.SHORT_TERM)
    memory.store_memory(content="用户对历史和美食感兴趣，特别关注意大利和法国。助手推荐了意大利的罗马和佛罗伦萨，以及法国的巴黎和里昂，指出这些城市的历史景点和美食特色。", memory_type=MemoryType.SHORT_TERM)
    memory.store_memory(content="用户对历史和美食感兴趣，特别关注意大利和法国的旅行。助手根据用户兴趣，推荐了意大利的罗马、佛罗伦萨和威尼斯，以及法国的巴黎、里昂和普罗旺斯地区，并为期两周的行程提供了详细建议，包括各城市的主要景点和美食体验。", memory_type=MemoryType.SHORT_TERM)
    print(memory.search_memory("用户要做什么"))