#!/usr/bin/env python3
"""任务追踪系统示例"""

import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from contextlib import contextmanager
from threading import local

from echo.schema.llm import Usage
from echo.schema.agent import AgentResponse
from echo.schema.task import ConversationTask, ConversationMessage
from echo.agent.core.agent import ConversationAgent


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
        self._sessions: Dict[str, ConversationTask] = {}
        self._current_session: Optional[ConversationTask] = None
        self._thread_local = local()
    
    def start_task(self, task_id: str, task_name: str) -> ConversationTask:
        """开始一个新任务"""
        session = ConversationTask(task_id=task_id, task_name=task_name)
        self._sessions[task_id] = session
        self._current_session = session
        self._thread_local.current_session = session
        return session
    
    def get_current_session(self) -> Optional[ConversationTask]:
        """获取当前会话"""
        return getattr(self._thread_local, "current_session", self._current_session)
    
    def finish_task(self, task_id: str) -> Optional[ConversationTask]:
        """结束任务"""
        session = self._sessions.get(task_id)
        if session:
            session.finish()
            if self._current_session == session:
                self._current_session = None
                self._thread_local.current_session = None
        return session
    
    def get_session(self, task_id: str) -> Optional[ConversationTask]:
        """获取指定任务的会话"""
        return self._sessions.get(task_id)
    
    def get_all_sessions(self) -> Dict[str, ConversationTask]:
        """获取所有会话"""
        return self._sessions.copy()
    
    def record_user_input(
        self, 
        content: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录用户输入
        
        Args:
            content: 用户输入内容
            metadata: 额外的元数据
        """
        record = ConversationMessage(
            timestamp=datetime.now(),
            role="user",
            content=content,
            metadata=metadata
        )
        session = self.get_current_session()
        if session:
            session.record(record)
    
    def record_assistant_response(
        self, 
        response: AgentResponse,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录助手响应
        
        Args:
            response: Agent响应，包含工具调用、检索文档等详细信息
            metadata: 额外的元数据
        """
        record = ConversationMessage(
            timestamp=datetime.now(),
            role="assistant",
            response=response,
            metadata=metadata
        )
        session = self.get_current_session()
        if session:
            session.record(record)
    
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
        record = ConversationMessage(
            timestamp=datetime.now(),
            role="system",
            content=f"RAG检索: {query}",
            metadata={"type": "rag_retrieval", "query": query, "retrieved_documents": retrieved_documents, "context_sources": sources}
        )
        session = self.get_current_session()
        if session:
            session.record(record)
    
    def add_iteration(self) -> None:
        """增加当前任务的迭代次数"""
        session = self.get_current_session()
        if session:
            session.iteration()
    
    def export_session_report(self, task_id: str) -> Optional[Dict[str, Any]]:
        """导出任务会话报告"""
        session = self.get_session(task_id)
        if session:
            return {
                "task_id": session.task_id,
                "task_name": session.task_name,
                "start_time": session.start_time.isoformat(),
                "end_time": session.end_time.isoformat() if session.end_time else None,
                "duration_seconds": session.get_duration(),
                "total_usage": session.total_usage,
                "iterations": session.iterations,
                "conversation_count": len(session.records),
                "conversations": [self._record_to_dict(record) for record in session.records]
            }
        return None
    
    def _record_to_dict(self, record: ConversationMessage) -> Dict[str, Any]:
        """将ConversationMessage转换为字典格式"""
        result = {
            "timestamp": record.timestamp.isoformat(),
            "role": record.role,
        }
        
        if record.role == "assistant" and record.response:
            result.update({
                "content": record.response.content,
                "finish_reason": record.response.finish_reason,
                "tool_calls": [{
                    "id": tc.get("id"),
                    "function": tc.get("function", {})
                } for tc in record.response.tool_calls] if record.response.tool_calls else None,
                "usage": record.response.usage
            })
        else:
            result.update({
                "content": record.content,
                "finish_reason": None,
                "tool_calls": None,
                "usage": None
            })
        
        # 添加元数据信息
        if record.metadata:
            result["metadata"] = record.metadata
            
        return result
    
    def export_all_reports(self) -> Dict[str, Dict[str, Any]]:
        """导出所有任务报告"""
        return {task_id: self.export_session_report(task_id) for task_id, session in self._sessions.items() if self.export_session_report(task_id)}


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