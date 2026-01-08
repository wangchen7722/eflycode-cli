"""主程序入口

将各个组件 Agent、UI、事件系统串联起来，实现完整的 CLI 应用
"""

import os
import threading
import time

from eflycode.core.agent.base import BaseAgent
from eflycode.core.agent.run_loop import AgentRunLoop
from eflycode.core.config import Config
from eflycode.core.config.config_manager import ConfigManager
from eflycode.core.context.manager import ContextManager
from eflycode.core.llm.protocol import DEFAULT_MAX_CONTEXT_LENGTH
from eflycode.core.llm.providers.openai import OpenAiProvider
from eflycode.core.mcp import MCPClient, MCPToolGroup, load_mcp_config
from eflycode.core.mcp.errors import MCPConnectionError, MCPConfigError
from eflycode.core.tool.file_system_tool import FILE_SYSTEM_TOOL_GROUP
from eflycode.core.tool.execute_command_tool import ExecuteCommandTool
from eflycode.core.ui.bridge import EventBridge
from eflycode.core.ui.errors import UserCanceledError
from eflycode.core.ui.renderer import Renderer
from eflycode.core.ui.ui_event_queue import UIEventQueue
from eflycode.cli.components.composer import ComposerComponent
from eflycode.cli.output import TerminalOutput
from eflycode.core.llm.advisors.request_log_advisor import RequestLogAdvisor
from eflycode.core.utils.logger import logger


def create_agent(config: Config) -> BaseAgent:
    """创建 Agent 实例

    Args:
        config: 配置对象

    Returns:
        BaseAgent: Agent 实例
    """
    # 使用文件系统工具组
    
    # 创建执行命令工具
    execute_command_tool = ExecuteCommandTool()

    # 获取最大上下文长度
    config_manager = ConfigManager.get_instance()
    max_context_length = config_manager.get_max_context_length()

    # 加载MCP工具
    tool_groups = [FILE_SYSTEM_TOOL_GROUP]
    mcp_clients = []
    
    try:
        mcp_server_configs = load_mcp_config()
        # 先启动所有MCP服务器的连接，不阻塞
        for server_config in mcp_server_configs:
            try:
                mcp_client = MCPClient(server_config)
                logger.info(f"启动MCP服务器连接: {server_config.name}")
                mcp_client.start_connect()
                mcp_clients.append(mcp_client)
            except Exception as e:
                logger.warning(
                    f"启动MCP服务器连接失败: {server_config.name}，"
                    f"错误类型: {type(e).__name__}，"
                    f"错误信息: {str(e)}，"
                    f"跳过该服务器"
                )
                continue
        
        # 等待所有连接完成并加载工具
        for mcp_client in mcp_clients:
            try:
                # 等待连接完成，超时时间5秒
                if not mcp_client.wait_for_connection(timeout=5):
                    logger.warning(
                        f"MCP服务器连接超时: {mcp_client.server_name}，跳过"
                    )
                    mcp_client.disconnect()
                    continue
                
                # 创建MCP工具组
                mcp_tool_group = MCPToolGroup(mcp_client)
                
                # 如果工具组中有工具，添加到工具组列表
                if mcp_tool_group.tools:
                    tool_groups.append(mcp_tool_group)
                    logger.info(
                        f"MCP工具组已加载: {mcp_client.server_name}，共{len(mcp_tool_group.tools)}个工具"
                    )
                else:
                    # 如果没有工具，断开连接
                    mcp_client.disconnect()
                    mcp_clients.remove(mcp_client)
                    logger.warning(f"MCP服务器未提供工具: {mcp_client.server_name}")
            except MCPConnectionError as e:
                logger.warning(
                    f"连接MCP服务器失败: {mcp_client.server_name}，"
                    f"错误: {e.message}，"
                    f"详情: {e.details if e.details else '无'}，"
                    f"跳过该服务器"
                )
                try:
                    mcp_client.disconnect()
                    mcp_clients.remove(mcp_client)
                except Exception:
                    pass
                continue
            except Exception as e:
                logger.warning(
                    f"加载MCP服务器失败: {mcp_client.server_name}，"
                    f"错误类型: {type(e).__name__}，"
                    f"错误信息: {str(e)}，"
                    f"跳过该服务器"
                )
                try:
                    mcp_client.disconnect()
                    mcp_clients.remove(mcp_client)
                except Exception:
                    pass
                continue
    except MCPConfigError as e:
        logger.warning(f"加载MCP配置失败: {e.message}，继续使用内置工具")
    except Exception as e:
        logger.warning(
            f"加载MCP配置时发生未知错误: {type(e).__name__}: {str(e)}，继续使用内置工具"
        )

    # 创建最终的 LLM Provider
    provider = OpenAiProvider(config.model_config)
    
    # 创建 Agent，SystemPromptAdvisor 会在 BaseAgent 初始化时自动创建
    agent = BaseAgent(
        model=config.model_name,
        provider=provider,
        tool_groups=tool_groups,
        tools=[execute_command_tool],
    )
    agent.max_context_length = max_context_length
    
    # 设置 Session 的上下文配置
    if config.context_config:
        agent.session.context_config = config.context_config
        if not agent.session.context_manager:
            agent.session.context_manager = ContextManager()

    # 保存MCP客户端引用，以便在shutdown时清理
    agent._mcp_clients = mcp_clients

    return agent


def run_agent_task(agent: BaseAgent, user_input: str, run_loop: AgentRunLoop) -> None:
    """在后台线程运行 Agent 任务

    Args:
        agent: Agent 实例
        user_input: 用户输入
        run_loop: AgentRunLoop 实例
    """
    try:
        run_loop.run(user_input)
    except Exception as e:
        agent.event_bus.emit("agent.error", agent=agent, error=e)


def run_interactive_cli(verbose: bool = False) -> None:
    """运行交互式 CLI

    Args:
        verbose: 是否启用详细日志模式，记录所有 LLM 请求和响应
    """
    
    logger.info("启动 eflycode CLI")
    if verbose:
        logger.info("详细日志模式已启用")
    
    # 加载配置
    config_manager = ConfigManager.get_instance()
    config = config_manager.load()
    logger.info(f"配置加载完成，工作区目录: {config.workspace_dir}")
    
    # 设置工作区目录
    workspace_dir = config.workspace_dir
    if workspace_dir:
        os.chdir(workspace_dir)
        logger.info(f"切换到工作区目录: {workspace_dir}")
    
    # 创建 Agent
    agent = create_agent(config)
    logger.info(f"Agent 创建完成，模型: {config.model_name}")

    # 如果启用了 verbose 模式，添加 RequestLogAdvisor
    if verbose:
        request_log_advisor = RequestLogAdvisor(session_id=agent.session.id)
        agent.provider.add_advisors([request_log_advisor])
        logger.info(f"RequestLogAdvisor 已添加，日志文件: {request_log_advisor.log_file}")
    
    # 创建 UI 组件
    ui_queue = UIEventQueue()
    output = TerminalOutput()
    renderer = Renderer(ui_queue, output)
    composer = ComposerComponent()
    
    # 创建事件桥接
    event_bridge = EventBridge(
        event_bus=agent.event_bus,
        ui_queue=ui_queue,
        event_types=[
            "agent.task.start",
            "agent.task.stop",
            "agent.message.start",
            "agent.message.delta",
            "agent.message.stop",
            "agent.tool.call.start",
            "agent.tool.call.ready",
            "agent.tool.call",
            "agent.tool.result",
            "agent.tool.error",
            "agent.error",
        ],
    )
    event_bridge.start()
    
    try:
        # 主循环
        while True:
            try:
                # 获取用户输入
                user_input = composer.show(
                    prompt_text="> ",
                    busy_prompt_text="🤔> ",
                    placeholder="share your ideas...",
                    toolbar_text="Press Ctrl+M to submit, Ctrl+D to exit",
                )
                
                if not user_input or not user_input.strip():
                    continue
                
                logger.info(f"收到用户输入: {user_input[:50]}...")
                
                session_messages = agent.session.get_messages()

                # 新任务开始时，检查session最后一条消息
                # 如果最后一条消息是tool消息，需要添加一个空的assistant消息来修复消息序列
                # 这样可以保持对话历史的连续性，同时确保消息序列正确
                if session_messages:
                    last_message = session_messages[-1]
                    if last_message.role == "tool":
                        # 最后一条是tool消息，添加一个空的assistant消息来结束上一个任务
                        # 这样可以保持消息序列正确，同时保留对话历史
                        logger.info("检测到session最后一条消息是tool消息，添加空的assistant消息以修复消息序列")
                        agent.session.add_message("assistant", content="")
                
                # 创建运行循环
                run_loop = AgentRunLoop(agent)
                
                # 在后台线程运行 Agent
                agent_thread = threading.Thread(
                    target=run_agent_task,
                    args=(agent, user_input, run_loop),
                    daemon=True,
                )
                agent_thread.start()
                
                # UI 渲染循环
                while agent_thread.is_alive():
                    # 处理 UI 事件
                    ui_queue.process_events(time_budget_ms=50)
                    
                    # 更新渲染
                    renderer.tick(time_budget_ms=50)
                    
                    # 短暂休眠，避免 CPU 占用过高
                    time.sleep(0.01)
                
                # 等待线程完成
                agent_thread.join(timeout=1.0)
                
                # 最终渲染
                while ui_queue.size() > 0:
                    ui_queue.process_events()
                    renderer.tick()
                
                renderer.tick()
                output.write("\n")
                
            except UserCanceledError:
                # 用户取消，按 Ctrl+D
                output.write("\n[退出]\n")
                break
            except KeyboardInterrupt:
                # Ctrl+C
                output.write("\n[中断]\n")
                break
            except Exception as e:
                output.show_error(e)
                logger.exception("主循环错误")
    
    finally:
        # 清理资源
        event_bridge.stop()
        renderer.close()
        
        # 断开MCP客户端连接
        if hasattr(agent, "_mcp_clients"):
            for mcp_client in agent._mcp_clients:
                try:
                    mcp_client.disconnect()
                except Exception as e:
                    logger.warning(f"断开MCP客户端连接失败: {e}")
        
        agent.shutdown()


def main() -> None:
    """主函数，用于向后兼容"""
    run_interactive_cli()


if __name__ == "__main__":
    main()

