#!/usr/bin/env python3
"""Token消耗统计系统示例"""

import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import contextmanager
from threading import local

from echo.schema.schema import Usage
from echo.agent.core.agent import ConversationAgent
from echo.schema.schema import AgentResponse


def add_usage(base_usage: Usage, new_usage: Usage) -> Usage:
    """合并两个Usage统计
    
    Args:
        base_usage: 基础使用统计
        new_usage: 新的使用统计
        
    Returns:
        Usage: 合并后的使用统计
    """
    return {
        "prompt_tokens": base_usage.get("prompt_tokens", 0) + new_usage.get("prompt_tokens", 0),
        "completion_tokens": base_usage.get("completion_tokens", 0) + new_usage.get("completion_tokens", 0),
        "total_tokens": base_usage.get("total_tokens", 0) + new_usage.get("total_tokens", 0)
    }


@dataclass
class ConversationRecord:
    """对话记录，支持RAG和复杂交互场景"""
    timestamp: datetime
    role: str  # "user", "assistant", "system", "tool"
    
    # 基础内容
    response: Optional[AgentResponse] = None  # 对于assistant角色
    user_content: Optional[str] = None  # 对于user角色
    
    # RAG相关上下文
    retrieved_documents: Optional[List[Dict[str, Any]]] = None  # 检索到的文档
    context_sources: Optional[List[str]] = None  # 上下文来源
    
    # 工具调用详情
    tool_execution_details: Optional[Dict[str, Any]] = None  # 工具执行的详细信息
    
    # 元数据
    metadata: Optional[Dict[str, Any]] = None  # 额外的元数据信息
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        base_dict = {
            "timestamp": self.timestamp.isoformat(),
            "role": self.role,
        }
        
        if self.role == "assistant" and self.response:
            base_dict.update({
                "content": self.response.content,
                "finish_reason": self.response.finish_reason,
                "tool_calls": [{
                    "id": tc.get("id"),
                    "function": tc.get("function", {})
                } for tc in self.response.tool_calls] if self.response.tool_calls else None,
                "usage": self.response.usage
            })
        else:
            base_dict.update({
                "content": self.user_content,
                "finish_reason": None,
                "tool_calls": None,
                "usage": None
            })
        
        # 添加RAG和上下文信息（仅在存在时）
        if self.retrieved_documents:
            base_dict["retrieved_documents"] = self.retrieved_documents
        if self.context_sources:
            base_dict["context_sources"] = self.context_sources
        if self.tool_execution_details:
            base_dict["tool_execution_details"] = self.tool_execution_details
        if self.metadata:
            base_dict["metadata"] = self.metadata
            
        return base_dict


@dataclass
class TaskSession:
    """任务会话记录"""
    task_id: str
    task_name: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    total_usage: Usage = field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    conversations: List[ConversationRecord] = field(default_factory=list)
    iterations: int = 0
    
    def add_conversation(self, record: ConversationRecord) -> None:
        """添加对话记录"""
        self.conversations.append(record)
        # 只有assistant角色的响应才有token使用统计
        if record.role == "assistant" and record.response and record.response.usage:
            self.total_usage = add_usage(self.total_usage, record.response.usage)
    
    def add_iteration(self) -> None:
        """增加迭代次数"""
        self.iterations += 1
    
    def finish(self) -> None:
        """结束任务会话"""
        self.end_time = datetime.now()
    
    def get_duration(self) -> Optional[float]:
        """获取任务持续时间（秒）"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.get_duration(),
            "total_usage": self.total_usage,
            "iterations": self.iterations,
            "conversation_count": len(self.conversations),
            "conversations": [conv.to_dict() for conv in self.conversations]
        }


class TaskTracker:
    """任务执行追踪器
    
    负责追踪和记录Agent任务执行过程中的各种信息，包括：
    - 用户输入和助手响应
    - Token使用统计
    - 任务迭代次数
    - RAG检索上下文
    - 任务执行时间
    - 工具调用详情
    """
    
    def __init__(self):
        self._sessions: Dict[str, TaskSession] = {}
        self._current_session: Optional[TaskSession] = None
        self._thread_local = local()
    
    def start_task(self, task_id: str, task_name: str) -> TaskSession:
        """开始一个新任务"""
        session = TaskSession(task_id=task_id, task_name=task_name)
        self._sessions[task_id] = session
        self._current_session = session
        self._thread_local.current_session = session
        return session
    
    def get_current_session(self) -> Optional[TaskSession]:
        """获取当前会话"""
        return getattr(self._thread_local, "current_session", self._current_session)
    
    def finish_task(self, task_id: str) -> Optional[TaskSession]:
        """结束任务"""
        session = self._sessions.get(task_id)
        if session:
            session.finish()
            if self._current_session == session:
                self._current_session = None
                self._thread_local.current_session = None
        return session
    
    def get_session(self, task_id: str) -> Optional[TaskSession]:
        """获取指定任务的会话"""
        return self._sessions.get(task_id)
    
    def get_all_sessions(self) -> Dict[str, TaskSession]:
        """获取所有会话"""
        return self._sessions.copy()
    
    def record_conversation(
        self, 
        role: str, 
        response: Optional[AgentResponse] = None,
        user_content: Optional[str] = None
    ) -> None:
        """记录对话"""
        session = self.get_current_session()
        if session:
            record = ConversationRecord(
                timestamp=datetime.now(),
                role=role,
                response=response if role == "assistant" else None,
                user_content=user_content if role == "user" else None
            )
            session.add_conversation(record)
    
    def record_user_input(
        self, 
        content: str, 
        context_sources: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录用户输入
        
        Args:
            content: 用户输入内容
            context_sources: 上下文来源，如文件路径、URL等
            metadata: 额外的元数据
        """
        record = ConversationRecord(
            timestamp=datetime.now(),
            role="user",
            user_content=content,
            context_sources=context_sources,
            metadata=metadata
        )
        session = self.get_current_session()
        if session:
            session.add_conversation(record)
    
    def record_assistant_response(
        self, 
        response: AgentResponse,
        retrieved_documents: Optional[List[Dict[str, Any]]] = None,
        tool_execution_details: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录助手响应
        
        Args:
            response: Agent响应
            retrieved_documents: RAG检索到的文档
            tool_execution_details: 工具执行详情
            metadata: 额外的元数据
        """
        record = ConversationRecord(
            timestamp=datetime.now(),
            role="assistant",
            response=response,
            retrieved_documents=retrieved_documents,
            tool_execution_details=tool_execution_details,
            metadata=metadata
        )
        session = self.get_current_session()
        if session:
            session.add_conversation(record)
    
    def record_rag_context(
        self,
        query: str,
        retrieved_documents: List[Dict[str, Any]],
        sources: List[str]
    ) -> None:
        """专门记录RAG检索上下文
        
        Args:
            query: 检索查询
            retrieved_documents: 检索到的文档
            sources: 文档来源
        """
        record = ConversationRecord(
            timestamp=datetime.now(),
            role="system",
            user_content=f"RAG检索: {query}",
            retrieved_documents=retrieved_documents,
            context_sources=sources,
            metadata={"type": "rag_retrieval", "query": query}
        )
        session = self.get_current_session()
        if session:
            session.add_conversation(record)
    
    def add_iteration(self) -> None:
        """增加当前任务的迭代次数"""
        session = self.get_current_session()
        if session:
            session.add_iteration()
    
    def export_session_report(self, task_id: str) -> Optional[Dict[str, Any]]:
        """导出任务会话报告"""
        session = self.get_session(task_id)
        return session.to_dict() if session else None
    
    def export_all_reports(self) -> Dict[str, Dict[str, Any]]:
        """导出所有任务报告"""
        return {task_id: session.to_dict() for task_id, session in self._sessions.items()}


# 全局任务追踪器实例
task_tracker = TaskTracker()


@contextmanager
def task_session(task_id: str, task_name: str):
    """任务会话上下文管理器"""
    session = task_tracker.start_task(task_id, task_name)
    try:
        yield session
    finally:
        task_tracker.finish_task(task_id)


# 所有Token追踪功能都通过TaskDrivenMixin实现


# ==================== 任务驱动混入（Mixin）方案 ====================

class TaskDrivenMixin:
    """任务驱动混入类，为Agent添加任务执行追踪和统计功能
    
    这个Mixin提供了任务级别的执行追踪，包括：
    - 用户输入记录
    - 迭代次数统计
    - Token使用量追踪
    - RAG上下文记录
    - 任务执行时间统计
    
    使用方式：
    class MyAgent(TaskDrivenMixin, Agent):
        pass
    """
    
    def __init__(self, *args, tracker: Optional['TaskTracker'] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._task_tracker = tracker or task_tracker
        self._task_driven_enabled = True
    
    def run(self, content: str, stream: bool = False):
        """任务驱动的run方法，自动追踪任务执行过程"""
        # 任务执行前置处理
        self._task_tracker.record_user_input(content)
        self._task_tracker.add_iteration()
        
        try:
            # 执行任务
            result = super().run(content, stream)
            
            # 任务执行后置处理
            if isinstance(result, AgentResponse):
                self._task_tracker.record_assistant_response(result)
            
            return result
        except Exception as e:
            # 任务执行异常处理
            raise


# TaskDrivenMixin是唯一的Token追踪方案


# 示例使用代码
def demo_proxy_pattern():
    """演示代理设计模式的Token追踪功能"""
    from echo.agent.registry import create_agent
    from echo.llm.openai_engine import OpenAIEngine

    # 创建LLM引擎（使用模拟配置）
    from echo.llm.llm_engine import LLMConfig
    
    llm_config: LLMConfig = {
        "model": "gpt-3.5-turbo",
        "base_url": "https://api.openai.com/v1",
        "api_key": "test-key"
    }
    
    llm_engine = OpenAIEngine(llm_config)
    
    try:
        # 创建原始Agent
        original_agent = create_agent("developer", llm_engine)
        
        print("=== 任务驱动Mixin方案演示 ===")
        
        # 创建使用TaskDrivenMixin的Agent
        print("\n创建任务驱动的开发者Agent:")
        class TaskDrivenDeveloper(TaskDrivenMixin, ConversationAgent):
            ROLE = "task_driven_developer"
            DESCRIPTION = "使用任务驱动Mixin的开发者Agent"
        
        task_driven_agent = TaskDrivenDeveloper(llm_engine)
        print(f"   创建成功: {task_driven_agent.__class__.__name__}")
        print(f"   任务追踪功能: {'已启用' if hasattr(task_driven_agent, '_task_driven_enabled') else '未启用'}")
        
        print("\n开始演示任务驱动Agent:")
        # 使用TaskDrivenMixin方案进行演示
        tracking_agent = task_driven_agent
        
        # 开始任务会话
        with task_session("task_001", "代码重构任务") as session:
            print(f"开始任务: {session.task_name}")
            
            # 模拟多轮对话
            responses = [
                "请帮我分析这段Python代码的性能问题",
                "如何优化这个函数的执行效率？",
                "请生成优化后的代码"
            ]
            
            for i, user_input in enumerate(responses, 1):
                print(f"\n=== 第{i}轮对话 ===")
                print(f"用户: {user_input}")
                
                try:
                    # 这里会自动追踪Token使用
                    response = tracking_agent.run(user_input)
                    print(f"助手: {response.content[:100]}...")
                except Exception as e:
                    print(f"模拟响应（实际需要真实API）: 收到请求 - {user_input}")
                    
                    # 检查Agent是否已有任务驱动功能
                    if not hasattr(tracking_agent, '_task_driven_enabled'):
                        # 只有在没有内置追踪功能时才手动记录
                        task_tracker.record_user_input(user_input)
                        task_tracker.add_iteration()
                    
                    # 手动记录模拟的AgentResponse
                    mock_usage = {
                        "prompt_tokens": 50 + i * 10,
                        "completion_tokens": 30 + i * 5,
                        "total_tokens": 80 + i * 15
                    }
                    
                    mock_response = AgentResponse(
                        content=f"这是第{i}轮的模拟响应内容",
                        finish_reason="stop",
                        tool_calls=None,
                        usage=mock_usage
                    )
                    
                    # 模拟RAG场景：记录检索到的文档
                    if i == 2:  # 第二轮模拟RAG检索
                        mock_documents = [
                            {"title": "Python性能优化指南", "content": "使用缓存可以显著提升性能...", "score": 0.95},
                            {"title": "算法复杂度分析", "content": "时间复杂度O(n)优于O(n²)...", "score": 0.87}
                        ]
                        task_tracker.record_rag_context(
                            query="Python函数优化方法",
                            retrieved_documents=mock_documents,
                            sources=["docs/performance.md", "docs/algorithms.md"]
                        )
                        
                        # 记录带RAG上下文的响应
                        task_tracker.record_assistant_response(
                            mock_response,
                            retrieved_documents=mock_documents,
                            metadata={"rag_enabled": True, "retrieval_method": "semantic_search"}
                        )
                    else:
                        task_tracker.record_assistant_response(mock_response)
        
        # 获取任务报告
        report = task_tracker.export_session_report("task_001")
        if report:
            print("\n=== 任务统计报告 ===")
            print(f"任务ID: {report['task_id']}")
            print(f"任务名称: {report['task_name']}")
            print(f"持续时间: {report['duration_seconds']:.2f}秒")
            print(f"总迭代次数: {report['iterations']}")
            print(f"对话轮数: {report['conversation_count']}")
            print(f"总Token消耗: {report['total_usage']}")
            
            print("\n=== 详细对话记录 ===")
            for i, conv in enumerate(report['conversations'], 1):
                print(f"{i}. [{conv['role']}] {conv['content'][:50]}...")
                if conv['usage']:
                    print(f"   Token使用: {conv['usage']}")
        
        # 保存报告到文件
        with open("token_usage_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print("\n报告已保存到 token_usage_report.json")
        
    except Exception as e:
        print(f"演示过程中出现错误: {e}")
        print("这是正常的，因为没有真实的API配置")


if __name__ == "__main__":
    print("代理设计模式Token追踪系统演示")
    print("=" * 50)
    demo_proxy_pattern()