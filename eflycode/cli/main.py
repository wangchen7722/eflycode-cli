"""主程序入口

将各个组件 Agent、UI、事件系统串联起来，实现完整的 CLI 应用
"""

import os
import threading
import time

from eflycode.core.agent.base import BaseAgent
from eflycode.core.agent.run_loop import AgentRunLoop
from eflycode.core.config import Config, get_max_context_length, load_config, load_config_from_file
from eflycode.core.context.manager import ContextManager
from eflycode.core.llm.protocol import DEFAULT_MAX_CONTEXT_LENGTH
from eflycode.core.llm.providers.openai import OpenAiProvider
from eflycode.core.tool.file_tool import create_file_tool_group
from eflycode.core.tool.execute_command_tool import ExecuteCommandTool
from eflycode.core.tool.finish_task_tool import FinishTaskTool
from eflycode.core.ui.bridge import EventBridge
from eflycode.core.ui.errors import UserCanceledError
from eflycode.core.ui.renderer import Renderer
from eflycode.core.ui.ui_event_queue import UIEventQueue
from eflycode.cli.components.composer import ComposerComponent
from eflycode.cli.output import TerminalOutput
from eflycode.core.utils.logger import logger


def create_agent(config: Config) -> BaseAgent:
    """创建 Agent 实例

    Args:
        config: 配置对象

    Returns:
        BaseAgent: Agent 实例
    """
    # 创建 LLM Provider
    provider = OpenAiProvider(config.model_config)

    # 创建文件工具组
    file_tool_group = create_file_tool_group()

    # 创建完成任务工具
    finish_task_tool = FinishTaskTool()
    
    # 创建执行命令工具
    execute_command_tool = ExecuteCommandTool()

    # 获取最大上下文长度
    max_context_length = DEFAULT_MAX_CONTEXT_LENGTH
    if config.config_file_path:
        try:
            config_data = load_config_from_file(config.config_file_path)
            max_context_length = get_max_context_length(config_data)
        except Exception:
            pass

    # 创建 Agent
    agent = BaseAgent(
        model=config.model_name,
        provider=provider,
        tool_groups=[file_tool_group],
        tools=[finish_task_tool, execute_command_tool],
    )
    agent.max_context_length = max_context_length
    
    # 设置 Session 的上下文配置
    if config.context_config:
        agent.session.context_config = config.context_config
        if not agent.session.context_manager:
            agent.session.context_manager = ContextManager()

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


def main() -> None:
    """主函数"""
    
    logger.info("启动 eflycode CLI")
    
    # 加载配置
    config = load_config()
    logger.info(f"配置加载完成，工作区目录: {config.workspace_dir}")
    
    # 设置工作区目录
    workspace_dir = config.workspace_dir
    if workspace_dir:
        os.chdir(workspace_dir)
        logger.info(f"切换到工作区目录: {workspace_dir}")
    
    # 创建 Agent
    agent = create_agent(config)
    logger.info(f"Agent 创建完成，模型: {config.model_name}")
    
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
        agent.shutdown()


if __name__ == "__main__":
    main()

