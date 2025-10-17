"""
Agent 运行循环模块

提供简洁的交互式 Agent 运行环境
"""

import json
import sys
from typing import Optional, List
from enum import Enum

from eflycode.ui.base_ui import BaseUI
from eflycode.agent.core.agent import ConversationAgent
from eflycode.ui.command.command_handler import CommandHandler
from eflycode.schema.agent import AgentResponseChunk, AgentResponseChunkType
from eflycode.schema.llm import ToolCall
from eflycode.util.logger import logger
from eflycode.util.event_bus import EventBus


class RunLoopState(Enum):
    """运行循环状态"""
    
    # 初始化中
    INITIALIZING = "initializing"
    # 就绪状态，已初始化完成
    READY = "ready"
    # 运行中，用户输入或 Agent 响应
    RUNNING = "running"
    # 中断中，正在处理中断信号
    INTERRUPTING = "interrupting"
    # 已中断，等待用户决定
    INTERRUPTED = "interrupted"
    # 关闭中，正在清理资源
    STOPPING = "stopping"
    # 已关闭，运行循环结束
    STOPPED = "stopped"


class AgentRunLoop:
    """Agent 运行循环"""
    
    def __init__(
        self,
        agent: ConversationAgent,
        ui: BaseUI,
        stream_output: bool = True,
        event_bus: Optional[EventBus] = None,
    ):
        """初始化运行循环
        
        Args:
            agent: 对话智能体实例
            ui: 用户界面实例
            stream_output: 是否使用流式输出
            event_bus: 事件总线实例
        """
        self.agent = agent
        self.ui = ui
        self.stream_output = stream_output
        self.event_bus = event_bus
        
        self._state = RunLoopState.INITIALIZING
        self._running = False
        self.command_handler = CommandHandler(ui, self)
        
        # 初始化完成，设置为就绪状态
        self._state = RunLoopState.READY
    
    @property
    def state(self) -> RunLoopState:
        """获取当前状态"""
        return self._state
    
    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running
    
    def run(self) -> None:
        """启动运行循环"""
        if self._running:
            self.ui.warning("运行循环已在运行中")
            return
        
        self._running = True
        self._state = RunLoopState.RUNNING
        
        logger.info("Starting agent run loop")
        
        try:
            self._show_welcome()
            
            while self._running:
                try:
                    user_input = self.ui.acquire_user_input()
                    
                    if not user_input.strip():
                        continue
                    
                    # 处理命令
                    if self.command_handler.is_command(user_input):
                        result = self.command_handler.handle_command(user_input)
                        
                        # 处理命令结果
                        if result.message:
                            if result.success:
                                self.ui.success(result.message)
                            else:
                                self.ui.error(result.message)
                        
                        if not result.continue_loop:
                            break
                        continue
                    
                    # 处理用户输入
                    self._process_user_input(user_input)
                    
                except KeyboardInterrupt:
                    self._state = RunLoopState.INTERRUPTING
                    self.ui.info("\n检测到中断信号")
                    self._state = RunLoopState.INTERRUPTED
                    sys.exit(0)
                    
                except Exception as e:
                    self.ui.error(f"处理输入时发生错误: {str(e)}")
                    logger.exception(f"Error processing input: {e}")
                    
                    try:
                        choice = self.ui.choices("是否继续运行？", ["是", "否"])
                        if choice == "否":
                            break
                    except KeyboardInterrupt:
                        break
                        
        except Exception as e:
            self.ui.error(f"运行循环发生致命错误: {str(e)}")
            logger.exception(f"Fatal error in run loop: {e}")
            
        finally:
            self._state = RunLoopState.STOPPING
            self._running = False
            # 清理资源...
            self._state = RunLoopState.STOPPED
            logger.info("Stopped agent run loop")
    
    def _show_welcome(self) -> None:
        """显示欢迎信息"""
        self.ui.welcome()

    def _process_user_input(self, user_input: str) -> None:
        """处理用户输入"""
        try:
            if self.stream_output and hasattr(self.agent, "stream"):
                self._handle_stream_response(user_input)
            else:
                self._handle_single_response(user_input)
            # 输出换行
            self.ui.print("")
        except Exception as e:
            self.ui.error(f"Agent 处理失败: {str(e)}")
            logger.exception(f"Agent processing failed: {e}")

    def _handle_stream_response(self, user_input: str) -> None:
        """处理流式响应"""
        response_stream = self.agent.stream(user_input)

        for chunk in response_stream:
            self._display_response_chunk(chunk)
    
    def _handle_single_response(self, user_input: str) -> None:
        """处理单次响应"""
        response = self.agent.call(user_input)

        if response.content:
            self.ui.print(response.content)
        
        if response.tool_calls:
            self._display_tool_calls(response.tool_calls)
    
    def _display_response_chunk(self, chunk: AgentResponseChunk) -> None:
        """显示响应块"""
        if chunk.type == AgentResponseChunkType.TEXT and chunk.content:
            self.ui.print(chunk.content, end="")
            self.ui.flush()
        elif chunk.type in [AgentResponseChunkType.TOOL_CALL_START, AgentResponseChunkType.TOOL_CALL_END] and chunk.tool_calls:
            self._display_tool_calls(chunk.tool_calls)
        elif chunk.type == AgentResponseChunkType.DONE:
            self.ui.print("\n")
    
    def _display_tool_calls(self, tool_calls: List[ToolCall]) -> None:
        """显示工具调用信息"""
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            try:
                tool_args = json.loads(tool_call.function.arguments)
                args_display = json.dumps(tool_args, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                args_display = tool_call.function.arguments
            
            self.ui.panel(
                [f"工具调用: {tool_name}"],
                f"参数:\n{args_display}" if args_display else "",
                color="blue"
            )
    
    def stop(self) -> None:
        """停止运行循环"""
        self._state = RunLoopState.STOPPING
        self._running = False
        # 清理资源...
        self._state = RunLoopState.STOPPED