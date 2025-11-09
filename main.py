from eflycode import get_application_context


def main():
    """主函数，启动 Developer agent 的交互式会话"""
    
    # 获取应用程序上下文
    app_context = get_application_context()
    
    # 启动应用程序上下文
    app_context.start()
    
    # 使用AgentRegistry创建developer agent
    agent_registry = app_context.get_agent_registry()
    llm_engine = app_context.create_llm_engine()
    developer = agent_registry.create_agent("developer", llm_engine)
    run_loop = app_context.create_agent_run_loop(agent=developer, stream_output=True)
    main_app = app_context.create_main_ui_app()
    
    main_app.initialize()
    run_loop.start_in_background()
    
    main_app.run()


if __name__ == "__main__":
    main()
