"""
Agent 运行循环模块

提供简洁的交互式 Agent 运行环境
"""

import json
from typing import Optional, Callable, List
from enum import Enum

from echo.ui.base_ui import BaseUI
from echo.agent.core.agent import ConversationAgent
from echo.ui.command.command_handler import CommandHandler
from echo.schema.agent import AgentResponseChunk, AgentResponseChunkType
from echo.schema.llm import ToolCall
from echo.util.logger import logger


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
        welcome_message: Optional[str] = None,
        stream_output: bool = True,
    ):
        """初始化运行循环
        
        Args:
            agent: 对话智能体实例
            ui: 用户界面实例
            welcome_message: 欢迎消息
            stream_output: 是否使用流式输出
        """
        self.agent = agent
        self.ui = ui
        self.welcome_message = welcome_message
        self.stream_output = stream_output
        
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
    
    def register_command(self, command: str, handler: Callable[[str], bool]):
        """注册自定义命令"""
        self.command_handler.register_command(command, handler)
    
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
                    user_input = self.ui.acquire_user_input(prompt="> ")
                    
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
                    continue
                    
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
        self.ui.welcome(f"欢迎使用 {self.agent.name}")
        self.ui.info("输入 /help 查看可用命令")
    
    def _process_user_input(self, user_input: str) -> None:
        """处理用户输入"""
        try:
            self.ui.info(f"\n[bold blue]{self.agent.name} 正在思考...[/bold blue]")
            
            if self.stream_output and hasattr(self.agent, "stream"):
                self._handle_stream_response(user_input)
            else:
                self._handle_single_response(user_input)
                
        except Exception as e:
            self.ui.error(f"Agent 处理失败: {str(e)}")
            logger.exception(f"Agent processing failed: {e}")
    
    def _handle_stream_response(self, user_input: str) -> None:
        """处理流式响应"""
        response_stream = self.agent.stream(user_input)
        self.ui.info(f"\n[bold green]{self.agent.name} 回复:[/bold green]")
        
        for chunk in response_stream:
            self._display_response_chunk(chunk)
    
    def _handle_single_response(self, user_input: str) -> None:
        """处理单次响应"""
        response = self.agent.call(user_input)
        self.ui.info(f"\n[bold green]{self.agent.name} 回复:[/bold green]")
        
        if response.content:
            self.ui.print(response.content)
        
        if response.tool_calls:
            self._display_tool_calls(response.tool_calls)
    
    def _display_response_chunk(self, chunk: AgentResponseChunk) -> None:
        """显示响应块"""
        if chunk.type == AgentResponseChunkType.TEXT and chunk.content:
            self.ui.print(chunk.content, end="")
            self.ui.flush()
        elif chunk.type == AgentResponseChunkType.TOOL_CALL and chunk.tool_calls:
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
            except:
                args_display = tool_call.function.arguments
            
            self.ui.panel(
                [f"工具调用: {tool_name}"],
                f"参数:\n{args_display}",
                color="blue"
            )
    
    def stop(self) -> None:
        """停止运行循环"""
        self._state = RunLoopState.STOPPING
        self._running = False
        # 清理资源...
        self._state = RunLoopState.STOPPED