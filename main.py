from eflycode.env import Environment
from eflycode.llm.openai_engine import OpenAIEngine
from eflycode.agent.developer import Developer
from eflycode.agent.run_loop import AgentRunLoop
from eflycode.ui.console.app import ConsoleAgentEventUI
from eflycode.util.event_bus import EventBus


def main():
    """主函数，启动 Developer agent 的交互式会话"""
    
    # 获取环境配置
    environment = Environment.get_instance()
    # 事件总线
    event_bus = EventBus()
    
    # 创建 LLM 引擎
    llm_engine = OpenAIEngine(
        llm_config=environment.get_llm_config(),
        advisors=["buildin_environment_advisor", "buildin_tool_call_advisor", "buildin_logging_advisor"]
    )
    
    # 创建 Developer agent
    developer = Developer(llm_engine=llm_engine)
    
    # 创建控制台 UI
    ui = ConsoleAgentEventUI(event_bus)
    
    # 创建运行循环
    run_loop = AgentRunLoop(
        agent=developer,
        ui=ui,
        stream_output=True,
        event_bus=event_bus,
    )
    
    # 启动运行循环
    run_loop.run()


if __name__ == "__main__":
    main()
