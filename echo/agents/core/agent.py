import json
import logging
import time
import uuid
from typing import (
    Any,
    Dict,
    Generator,
    List,
    Optional,
    Sequence,
    overload,
    Literal,
)
from datetime import datetime

from echo.utils.logger import get_logger
from echo.llms.llm_engine import LLMEngine
from echo.llms.schema import ChatCompletionChunk, Message, ToolCall, Usage
from echo.prompt.prompt_loader import PromptLoader
from echo.tools.base_tool import BaseTool
from echo.utils.tool_utils import apply_tool_calls_template
from echo.utils.config import get_global_config
from echo.parsers import StreamResponseParser
from echo.agents.schema import (
    AgentResponseChunk,
    AgentResponseChunkType,
    AgentResponse,
    AgentMessageParserResult,
)
from echo.agents.core.context_compressor import ContextCompressor
from echo.agents.core.context_retriever import ContextRetriever
from echo.agents.core.memory_manager import MemoryManager
from echo.config import (
    CompressionConfig, CompressionStrategy,
    RetrievalConfig, RetrievalStrategy,
    MemoryConfig, MemoryType, MemoryImportance
)

logger: logging.Logger = get_logger()


def agent_message_stream_parser(
        tools: Sequence[BaseTool],
        chat_completion_chunk_stream_generator: Generator[ChatCompletionChunk, None, None],
) -> Generator[AgentResponseChunk, None, None]:
    """使用StateMachineStreamParser解析流式响应中的工具调用
    
    Args:
        tools: 可用的工具列表
        chat_completion_chunk_stream_generator: 聊天完成块的流式生成器
        
    Yields:
        AgentResponseChunk: 解析后的响应块
    """
    parser = StreamResponseParser(tools)
    yield from parser.parse_stream(chat_completion_chunk_stream_generator)

class Agent:
    """基础智能体类"""

    ROLE = "base"
    DESCRIPTION = "一个通用对话智能助手"

    def __init__(
        self,
        llm_engine: LLMEngine,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tools: Optional[Sequence[BaseTool]] = None,
        system_prompt: Optional[str] = None,
        # 新增的企业级功能配置
        compression_config: Optional[CompressionConfig] = None,
        retrieval_config: Optional[RetrievalConfig] = None,
        memory_config: Optional[MemoryConfig] = None,
        enable_context_compression: bool = True,
        enable_context_retrieval: bool = True,
        enable_memory_management: bool = True,
        **kwargs,
    ):
        """初始化智能体
        Args:
            name: 智能体名称
            llm_engine: 语言模型引擎
            description: 智能体描述
            tools: 初始工具字典
            compression_config: 上下文压缩配置
            retrieval_config: 上下文检索配置
            memory_config: 记忆管理配置
            enable_context_compression: 是否启用上下文压缩
            enable_context_retrieval: 是否启用上下文检索
            enable_memory_management: 是否启用记忆管理
            **kwargs: 其他参数
        """
        self._name = name or self.ROLE
        self._description = description or self.DESCRIPTION
        self._system_prompt = system_prompt
        self.llm_engine = llm_engine
        self.kwargs = kwargs
        
        # 企业级功能开关
        self.enable_context_compression = enable_context_compression
        self.enable_context_retrieval = enable_context_retrieval
        self.enable_memory_management = enable_memory_management
        
        # 获取全局配置
        self._global_config = get_global_config()
        self._history_messages: List[Message] = []
        self._history_messages_limit = 10
        # 初始化工具
        self.auto_approve = kwargs.get("auto_approve", False)

        self._tools = tools or []
        self._tool_map = {tool.name: tool for tool in self._tools}

        # 初始化上下文压缩器
        if self.enable_context_compression:
            self.compression_config = compression_config or CompressionConfig(
                strategy=CompressionStrategy.HYBRID,
                max_tokens=4000,
                compression_ratio=0.3
            )
            self.context_compressor = ContextCompressor(self.compression_config, self.llm_engine)
        else:
            self.context_compressor = None
        
        # 初始化上下文检索器
        if self.enable_context_retrieval:
            self.retrieval_config = retrieval_config or RetrievalConfig(
                strategy=RetrievalStrategy.HYBRID,
                max_results=10,
                similarity_threshold=0.7
            )
            self.context_retriever = ContextRetriever(self.retrieval_config, self.llm_engine)
        else:
            self.context_retriever = None
        
        # 初始化记忆管理器
        if self.enable_memory_management:
            self.memory_config = memory_config or MemoryConfig(
                short_term_capacity=50,
                long_term_capacity=1000,
                enable_persistence=True
            )
            self.memory_manager = MemoryManager(self.memory_config, self.llm_engine)
        else:
            self.memory_manager = None

    @property
    def tools(self) -> Sequence[BaseTool]:
        """获取工具字典"""
        return self._tools

    @property
    def role(self):
        return self.ROLE.strip()

    @property
    def name(self):
        return self._name.strip()

    @property
    def description(self):
        return self.DESCRIPTION.strip()

    def system_prompt(self) -> str:
        """渲染系统提示词"""
        if self._system_prompt:
            return self._system_prompt
        # system_info = get_system_info()
        # workspace_info = get_workspace_info(system_info["work_dir"])
        return PromptLoader.get_instance().render_template(
            f"{self.role}/system.prompt",
            name=self.name,
            role=self.role,
            tools=self.tools,
            # system_info=system_info,
            # workspace=workspace_info
        )


    # def retrieve_memories(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    #     """检索相关记忆
    #
    #     Args:
    #         query: 查询文本
    #         top_k: 返回结果数量
    #
    #     Returns:
    #         List[MemoryItem]: 相关记忆列表
    #     """
    #     if self.memory.is_empty():
    #         return []
    #
    #     # 从短期和长期记忆中检索
    #     agent_memories = self.memory.search_memory(query, top_k=10)
    #
    #     return [memory.to_message() for memory in agent_memories]

    def _preprocess_messages(self, messages: List[Message]) -> List[Message]:
        """预处理消息列表，添加系统提示词和角色信息

        Args:
            messages: 消息列表

        Returns:
            List[Dict[str, Any]]: 预处理后的消息列表
        """
        # 将 tool_call 的格式变为 message 格式
        new_messages = []
        for message in messages:
            tool_calls = message.get("tool_calls", None)
            if tool_calls:
                new_messages.append(
                    {
                        "role": "assistant",
                        "content": apply_tool_calls_template(tool_calls),
                    }
                )
            else:
                new_messages.append(message)
        if new_messages[0]["role"] != "system":
            new_messages.insert(0, {"role": "system", "content": self.system_prompt()})
        
        # 应用上下文压缩
        if self.context_compressor and len(new_messages) > 5:
            compression_result = self.context_compressor.compress_messages(new_messages)
            new_messages = compression_result.compressed_messages
            
            logger.info(
                f"上下文压缩: {compression_result.original_count} -> {compression_result.compressed_count} 消息, "
                f"压缩比: {compression_result.compression_ratio:.2f}"
            )
        
        return new_messages

    def _run_no_stream(
            self, messages: List[Message], **kwargs
    ) -> AgentResponse:
        response = self.llm_engine.generate(messages=messages, stream=False, **kwargs)
        self._history_messages.append(response["choices"][0]["message"])
        return AgentResponse(
            content=response["choices"][0]["message"].get("content", None),
            finish_reason=response["choices"][0]["finish_reason"],
            tool_calls=response["choices"][0]["message"].get("tool_calls", None),
            usage=response["usage"],
        )

    def _run_stream(
            self, messages: List[Message], **kwargs
    ) -> Generator[AgentResponseChunk, None, None]:
        stream_interval = kwargs.get("stream_interval", 3)
        response = self.llm_engine.generate(messages=messages, stream=True, **kwargs)
        response_content = ""
        last_chunk: Optional[AgentResponseChunk] = None
        buffer = ""
        for chunk in agent_message_stream_parser(self.tools, response):
            if chunk.content:
                response_content += chunk.content
            if last_chunk is None:
                # 第一个块
                last_chunk = chunk
            if chunk.type == last_chunk.type:
                # 合并连续的文本块
                buffer += chunk.content
                if len(buffer) >= stream_interval:
                    yield AgentResponseChunk(
                        type=chunk.type,
                        content=buffer,
                        finish_reason=chunk.finish_reason,
                        tool_calls=chunk.tool_calls,
                        usage=chunk.usage,
                    )
                    buffer = ""
            else:
                # 输出上一个块
                if buffer:
                    yield AgentResponseChunk(
                        type=last_chunk.type,
                        content=buffer,
                        finish_reason=last_chunk.finish_reason,
                        tool_calls=last_chunk.tool_calls,
                        usage=last_chunk.usage,
                    )
                    buffer = ""
                yield chunk
            last_chunk = chunk
        self._history_messages.append(
            {"role": "assistant", "content": response_content}
        )
        # logger.debug(f"{self.name}: {response_content}")
        # logger.debug(
        #     json.dumps({
        #         "messages": messages,
        #         "response": response_content,
        #     })
        # )
    
    @overload 
    def run(self, content: str, stream: Literal[False] = False) -> AgentResponse:
        ...

    @overload
    def run(self, content: str, stream: Literal[True]) -> Generator[AgentResponseChunk, None, None]:
       ...

    def run(self, content: str, stream: bool = False, context: Optional[Dict[str, Any]] = None) -> AgentResponse | Generator[AgentResponseChunk, None, None]:
        """运行智能体，处理用户输入并生成响应

        Args:
            content: 用户输入的消息
            stream: 是否流式输出
            context: 额外的上下文信息

        Returns:
            AgentResponse: 智能体的响应结果
        """
        # 添加用户输入到记忆管理器
        if self.memory_manager:
            self.memory_manager.add_memory(
                content=content,
                memory_type=MemoryType.SHORT_TERM,
                tags={"user_input", "conversation"}
            )
        
        # 检索相关上下文
        relevant_context = []
        if self.context_retriever and len(self._history_messages) > 1:
            retrieval_response = self.context_retriever.retrieve_context(
                query=content,
                messages=self._history_messages,
                current_time=datetime.now()
            )
            relevant_context = [result.message for result in retrieval_response.results[:3]]
        
        # 构建消息列表
        messages = self._history_messages.copy()
        
        # 添加相关上下文
        if relevant_context:
            context_content = "相关上下文信息：\n" + "\n".join([
                f"- {msg.get('content', '')[:100]}..." for msg in relevant_context
            ])
            messages.append({"role": "system", "content": context_content})
        
        messages.append({"role": "user", "content": content})
        messages = self._preprocess_messages(messages)
        self._history_messages.append({"role": "user", "content": content})

        if stream:
            response = self._run_stream(messages, stream_interval=5)
        else:
            response = self._run_no_stream(messages)
        return response

    def execute_tool(self, tool_call: ToolCall) -> str:
        """执行工具调用

        Args:
            tool_call: 工具调用
        """
        tool_name = tool_call["function"]["name"]
        tool_call_arguments = json.loads(tool_call["function"]["arguments"])
        tool = self._tool_map.get(tool_name, None)
        if not tool:
            return f"未找到工具：{tool_name}"
        try:
            tool_response = tool.run(**tool_call_arguments)
            
            # 记录工具执行到记忆管理器
            if self.memory_manager:
                tool_memory_content = f"执行工具 {tool_name}，参数: {json.dumps(tool_call_arguments, ensure_ascii=False)[:200]}"
                self.memory_manager.add_memory(
                    content=tool_memory_content,
                    memory_type=MemoryType.SHORT_TERM,
                    importance=MemoryImportance.MEDIUM,
                    tags={"tool_execution", tool_name}
                )
            
            return f"This is system-generated message.\nThe result of tool call ({tool_name}) is shown below:\n{tool_response}"
        except Exception as e:
            # 记录错误到记忆管理器
            if self.memory_manager:
                error_content = f"工具 {tool_name} 执行失败: {str(e)}"
                self.memory_manager.add_memory(
                    content=error_content,
                    memory_type=MemoryType.SHORT_TERM,
                    importance=MemoryImportance.HIGH,
                    tags={"tool_error", tool_name, "error"}
                )
            
            return f"工具调用失败：{e}"
    
    # 新增的企业级功能方法
    
    def add_to_memory(self, content: str, memory_type: MemoryType = MemoryType.SHORT_TERM, 
                     importance: Optional[MemoryImportance] = None, tags: Optional[set] = None) -> Optional[str]:
        """添加内容到记忆管理器"""
        if not self.memory_manager:
            logger.warning("记忆管理器未启用")
            return None
        
        return self.memory_manager.add_memory(
            content=content,
            memory_type=memory_type,
            importance=importance,
            tags=tags
        )
    
    def search_memory(self, query: str, memory_type: Optional[MemoryType] = None) -> List:
        """搜索记忆"""
        if not self.memory_manager:
            logger.warning("记忆管理器未启用")
            return []
        
        return self.memory_manager.search_memories(query, memory_type)
    
    def consolidate_memories(self) -> int:
        """整合记忆（短期转长期）"""
        if not self.memory_manager:
            return 0
        
        return self.memory_manager.consolidate_memories()
    
    def cleanup_memories(self) -> int:
        """清理过期记忆"""
        if not self.memory_manager:
            return 0
        
        return self.memory_manager.cleanup_expired_memories()
    
    def get_agent_stats(self) -> Dict[str, Any]:
        """获取Agent统计信息"""
        stats = {
            "name": self.name,
            "description": self.description,
            "tools_count": len(self._tool_map),
            "available_tools": list(self._tool_map.keys()),
            "conversation_length": len(self._history_messages),
            "features": {
                "context_compression": self.enable_context_compression,
                "context_retrieval": self.enable_context_retrieval,
                "memory_management": self.enable_memory_management
            }
        }
        
        # 添加记忆统计
        if self.memory_manager:
            stats["memory_stats"] = self.memory_manager.get_memory_stats()
        
        # 添加压缩统计
        if self.context_compressor:
            stats["compression_stats"] = self.context_compressor.get_compression_stats(self._history_messages)
        
        # 添加检索统计
        if self.context_retriever:
            stats["retrieval_stats"] = self.context_retriever.get_retrieval_stats(self._history_messages)
        
        return stats
    
    def update_compression_config(self, config: CompressionConfig):
        """更新压缩配置"""
        if self.context_compressor:
            self.context_compressor.update_config(config)
            self.compression_config = config
    
    def update_retrieval_config(self, config: RetrievalConfig):
        """更新检索配置"""
        if self.context_retriever:
            self.context_retriever.update_config(config)
            self.retrieval_config = config
    
    def clear_conversation_history(self):
        """清空对话历史"""
        self._history_messages.clear()
        logger.info("对话历史已清空")
    
    def export_conversation(self) -> List[Dict[str, Any]]:
        """导出对话历史"""
        return [{
            "role": msg.get("role"),
            "content": msg.get("content"),
            "timestamp": msg.get("timestamp").isoformat() if msg.get("timestamp") else None
        } for msg in self._history_messages]
    
    def import_conversation(self, conversation_data: List[Dict[str, Any]]):
        """导入对话历史"""
        self._history_messages.clear()
        for msg_data in conversation_data:
            msg = {
                "role": msg_data.get("role"),
                "content": msg_data.get("content")
            }
            if msg_data.get("timestamp"):
                msg["timestamp"] = datetime.fromisoformat(msg_data["timestamp"])
            self._history_messages.append(msg)
        
        logger.info(f"导入了 {len(conversation_data)} 条对话记录")