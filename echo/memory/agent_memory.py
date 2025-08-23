import uuid
from abc import abstractmethod
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from langchain_chroma.vectorstores import Chroma
from langchain_community.docstore.document import Document
from langchain_huggingface.embeddings import HuggingFaceEmbeddings

from echo.llms.llm_engine import LLMEngine
from echo.llms.schema import ChatCompletion
from echo.memory.schema import MemoryItem, MemoryItemType


class AgentMemory:
    """
    智能体记忆实现
    """
    
    @abstractmethod
    def add(self, *args, **kwargs):
        """添加新的记忆"""
        raise NotImplementedError
    
    # @abstractmethod
    # def get(self, memory_id: str, *args, **kwargs):
    #     """根据唯一标识符获取对应的记忆"""
    #     raise NotImplementedError
    
    # @abstractmethod
    # def update(self, memory_id: str, *args, **kwargs):
    #     """根据唯一标识符更新记忆"""
    #     raise NotImplementedError
    
    # @abstractmethod
    # def delete(self, memory_id: str, *args, **kwargs):
    #     """根据唯一标识符删除记忆"""
    #     raise NotImplementedError
    
    @abstractmethod
    def search(self, query: str, *args, **kwargs) -> List[MemoryItem]:
        """根据查询条件搜索记忆"""
        raise NotImplementedError
    
    @abstractmethod
    def list_all(self, *args, **kwargs) -> List[MemoryItem]:
        """列出所有记忆"""
        raise NotImplementedError
    

class SummarizedAgentMemory(AgentMemory):
    
    SYSTEM_PROMPT = """"""
    
    def __init__(self, llm_engine: LLMEngine, summary_threshold: int = 40_000):
        self.llm_engine = llm_engine

        self._memories: List[MemoryItem] = []

        self.summary_threshold = summary_threshold
        self._summary_future: Optional[Future] = None
        self._executor = ThreadPoolExecutor(max_workers=1)
        
    def _render_summary_messages(self) -> List[Dict[str, Any]]:
        ...
        
    def _summary_memory(self) -> str:
        summary_messages = self._render_summary_messages()
        summary_response: ChatCompletion = self.llm_engine.generate(summary_messages, stream=False)
        context = summary_response.choices[0].message.content
        self._memories = [MemoryItem(
            id=str(uuid.uuid4()),
            type=MemoryItemType.CONTEXT,
            content=context,
            metadata={}
        )]
        

    def _maybe_schedule_summary(self):
        """检查当前所有消息是否超过摘要阈值，如果超过且没有摘要任务正在运行，则异步调度摘要任务。"""
        combined_text = ""
        for memory_item in self._memories:
            if memory_item.type == MemoryItemType.MESSAGES:
                for message in memory_item.content:
                    combined_text += message["content"] + "\n"
            elif memory_item.type == MemoryItemType.CONTEXT:
                combined_text += memory_item.content + "\n"
            else:
                raise ValueError(f"未知的记忆类型: {memory_item.type}")
        if len(combined_text) > self.summary_threshold:
            if self._summary_future is None or self._summary_future.done():
                self._summary_future = self._executor.submit(self._summary_memory)
            
        
    def add(self, messages: List[Dict[str, Any]]):
        memory_id = str(uuid.uuid4())
        memory_item = MemoryItem(
            id=memory_id,
            type=MemoryItemType.MESSAGES,
            content=messages,
            metadata={}
        )
        self._memories.append(memory_item)
        self._maybe_schedule_summary()
        return memory_id
    
    def search(self, query: str) -> List[MemoryItem]:
        return self._memories
    
    def list_all(self) -> List[MemoryItem]:
        return self._memories