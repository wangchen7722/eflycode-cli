"""主程序入口

将各个组件 Agent、UI、事件系统串联起来，实现完整的 CLI 应用
"""

import asyncio
import os
import time
from dataclasses import dataclass

from eflycode.cli.components.composer import ComposerComponent
from eflycode.cli.command_registry import get_command_registry
from eflycode.cli.output import TerminalOutput
from eflycode.core.agent.base import BaseAgent
from eflycode.core.agent.run_loop import AgentRunLoop
from eflycode.core.config import Config
from eflycode.core.config.config_manager import ConfigManager, get_user_config_dir
from eflycode.core.context.manager import ContextManager
from eflycode.core.agent.session_store import SessionStore
from eflycode.core.llm.advisors.request_log_advisor import RequestLogAdvisor
from eflycode.core.llm.providers.openai import OpenAiProvider
from eflycode.core.mcp import MCPClient, MCPToolGroup, load_mcp_config
from eflycode.core.mcp.errors import MCPConnectionError, MCPConfigError
from eflycode.core.skills import SkillsManager
from eflycode.core.skills.activate_tool import ActivateSkillTool
from eflycode.core.skills.skills_advisor import SkillsAdvisor
from eflycode.core.tool.execute_command_tool import ExecuteCommandTool
from eflycode.core.tool.file_system_tool import FILE_SYSTEM_TOOL_GROUP
from eflycode.core.ui.bridge import EventBridge
from eflycode.core.ui.errors import UserCanceledError
from eflycode.core.ui.renderer import Renderer
from eflycode.core.ui.ui_event_queue import UIEventQueue
from eflycode.core.utils.file_manager import get_file_manager
from eflycode.core.utils.logger import logger
from eflycode.core.event.event_bus import get_global_event_bus


@dataclass
class ApplicationContext:
    """应用上下文"""

    config: Config
    ui_queue: UIEventQueue | None = None
    output: TerminalOutput | None = None
    renderer: Renderer | None = None
    event_bridge: EventBridge | None = None


def initialize_application(setup_ui: bool = False) -> ApplicationContext:
    """初始化应用程序
    
    加载配置、设置工作区目录，执行应用程序初始化
    
    Returns:
        ApplicationContext: 应用上下文
    """
    logger.info("初始化应用程序")
    
    # 加载配置
    config_manager = ConfigManager.get_instance()
    config = config_manager.load()
    logger.info(f"配置加载完成，工作区目录: {config.workspace_dir}")
    
    # 设置工作区目录
    if config.workspace_dir:
        os.chdir(config.workspace_dir)
        logger.info(f"切换到工作区目录: {config.workspace_dir}")
    
    app_context = ApplicationContext(config=config)

    if setup_ui:
        ui_queue = UIEventQueue()
        output = TerminalOutput()
        renderer = Renderer(ui_queue, output)
        event_bridge = EventBridge(
            event_bus=get_global_event_bus(),
            ui_queue=ui_queue,
            event_types=[
                "app.startup",
                "app.initialized",
                "app.shutdown",
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

        app_context.ui_queue = ui_queue
        app_context.output = output
        app_context.renderer = renderer
        app_context.event_bridge = event_bridge

        event_bus = get_global_event_bus()
        event_bus.emit("app.startup")
        event_bus.emit("app.initialized", config=config)

        deadline = time.monotonic() + 0.2
        while time.monotonic() < deadline:
            ui_queue.process_events()
            renderer.tick()
            if ui_queue.size() == 0:
                time.sleep(0.01)
            else:
                time.sleep(0)

    return app_context


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

    # 初始化 SkillsManager（如果启用 skills 功能）
    user_config_dir = get_user_config_dir()
    project_workspace_dir = config.workspace_dir

    if config.skills_enabled:
        try:
            skills_manager = SkillsManager.get_instance()
            skills_manager.initialize(
                user_config_dir=user_config_dir,
                project_workspace_dir=project_workspace_dir,
            )
            logger.info("Skills 功能已启用")
        except Exception as e:
            logger.warning(f"初始化 SkillsManager 失败: {e}，禁用 skills 功能")
            config.skills = None  # type: ignore

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
    provider = OpenAiProvider(config.llm_config)

    # 创建 HookSystem
    from eflycode.core.hooks.system import HookSystem
    from pathlib import Path

    workspace_dir = config.workspace_dir or Path.cwd()
    hook_system = HookSystem(workspace_dir=workspace_dir)

    # 准备工具列表
    tools = [execute_command_tool]
    advisors = []

    # 如果启用 skills 功能，添加 ActivateSkillTool 和 SkillsAdvisor
    if config.skills_enabled:
        try:
            activate_skill_tool = ActivateSkillTool()
            tools.append(activate_skill_tool)
            skills_advisor = SkillsAdvisor(agent=None, config=config)  # type: ignore
            advisors.append(skills_advisor)
            logger.info("已添加 ActivateSkillTool 和 SkillsAdvisor")
        except Exception as e:
            logger.warning(f"添加 skills 相关组件失败: {e}")

    # 创建 Agent，SystemPromptAdvisor 会在 BaseAgent 初始化时自动创建
    agent = BaseAgent(
        model=config.model_name,
        provider=provider,
        tool_groups=tool_groups,
        tools=tools,
        advisors=advisors if advisors else None,
        hook_system=hook_system,
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


def _render_resumed_history(output: TerminalOutput, session_messages: list) -> None:
    """渲染恢复会话的历史消息"""
    if not session_messages:
        return
    output.write("\n[已恢复历史消息]\n")
    for message in session_messages:
        content = message.content or ""
        role = message.role
        if role == "tool":
            continue
        if role == "assistant" and message.tool_calls:
            for tool_call in message.tool_calls:
                args = tool_call.function.arguments or ""
                args_preview = args if len(args) <= 120 else f"{args[:120]}..."
                output.write(f"\n[tool] {tool_call.function.name} {args_preview}\n")
        output.write(f"\n{role}: {content}\n")
    output.write("\n")

async def run_interactive_cli(
    resume_session_id: str | None = None,
    app_context: ApplicationContext | None = None,
) -> None:
    """运行交互式 CLI

    Args:
        resume_session_id: 要恢复的会话 ID
        app_context: 应用上下文，可选
    """
    
    logger.info("启动 eflycode CLI")

    if not app_context:
        app_context = initialize_application(setup_ui=True)
    if not app_context.ui_queue or not app_context.output or not app_context.renderer:
        raise RuntimeError("应用上下文未初始化 UI 组件")
    if not app_context.event_bridge:
        raise RuntimeError("应用上下文未初始化 EventBridge")

    config = app_context.config
    logger.info(f"使用配置，工作区目录: {config.workspace_dir}")
    
    # 创建 Agent
    agent = create_agent(config)
    logger.info(f"Agent 创建完成，模型: {config.model_name}")

    session_data = None
    if resume_session_id:
        session_data = SessionStore.get_instance().load(resume_session_id)
        if not session_data:
            raise ValueError(f"未找到会话: {resume_session_id}")
        agent.session.load_state(
            session_id=session_data["id"],
            messages=session_data["messages"],
            initial_user_question=session_data.get("initial_user_question"),
        )
        logger.info(f"已恢复会话: {agent.session.id}")

    # 默认启用请求日志
    request_log_advisor = RequestLogAdvisor(session_id=agent.session.id)
    agent.provider.add_advisors([request_log_advisor])
    logger.info(f"RequestLogAdvisor 已添加，日志文件: {request_log_advisor.log_file}")
    
    # UI 组件从初始化上下文获取
    ui_queue = app_context.ui_queue
    output = app_context.output
    renderer = app_context.renderer
    file_manager = get_file_manager()
    file_manager.start_watching()
    # 创建智能命令 completer
    composer = ComposerComponent()
    smart_completer = composer.get_completer()
    registry = get_command_registry()
    
    event_bridge = app_context.event_bridge
    if session_data:
        _render_resumed_history(output, agent.session.get_messages())
    
    try:
        # 主循环
        while True:
            try:
                # 获取用户输入
                user_input = await composer.show(
                    prompt_text="> ",
                    busy_prompt_text="🤔> ",
                    placeholder="share your ideas...",
                    toolbar_text="Press Ctrl+M to submit, Ctrl+D to exit, /model to select model",
                )
                
                if not user_input or not user_input.strip():
                    continue

                if user_input.strip().startswith("/"):
                    handled = await registry.handle_command_async(user_input)
                    if handled:
                        continue
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
                
                # 使用 asyncio.to_thread 在线程中运行同步的 Agent 任务
                # 这样可以避免阻塞事件循环
                # 同时在前台处理 UI 更新
                agent_task = asyncio.create_task(
                    asyncio.to_thread(run_agent_task, agent, user_input, run_loop)
                )
                
                # UI 渲染循环，在 Agent 执行期间持续更新
                while not agent_task.done():
                    # 处理 UI 事件
                    ui_queue.process_events(time_budget_ms=50)
                    
                    # 更新渲染
                    renderer.tick(time_budget_ms=50)
                    
                    # 短暂休眠，避免 CPU 占用过高
                    await asyncio.sleep(0.01)
                
                # 等待任务完成，如果还没完成
                try:
                    await agent_task
                except Exception as e:
                    logger.error(f"Agent 任务执行失败: {e}", exc_info=True)
                
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
        get_global_event_bus().emit("app.shutdown")
        event_bridge.stop()
        renderer.close()
        file_manager.stop_watching()
        
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
    asyncio.run(run_interactive_cli())


if __name__ == "__main__":
    main()
