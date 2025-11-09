from eflycode import get_application_context
from eflycode.agent.event_controller import AgentEventController
from eflycode.llm.openai_engine import OpenAIEngine
from eflycode.ui.console.main_app import MainUIApplication



def main():
    """主函数，启动 Developer agent 的交互式会话"""

    # 获取应用程序上下文
    app_context = get_application_context()

    # 启动应用程序上下文
    app_context.start()

    agent_registry = app_context.get_agent_registry()
    llm_advisors = [
        "buildin_environment_advisor",
        "buildin_tool_call_advisor",
        "buildin_logging_advisor",
    ]
    llm_engine = OpenAIEngine(
        llm_config=app_context.get_environment().get_llm_config(), advisors=llm_advisors
    )
    developer = agent_registry.create_agent("developer", llm_engine)
    run_loop = AgentEventController(
        agent=developer, event_bus=app_context.get_event_bus(), stream_output=True
    )
    main_app = MainUIApplication(app_context.get_event_bus())

    main_app.run()


if __name__ == "__main__":
    main()
