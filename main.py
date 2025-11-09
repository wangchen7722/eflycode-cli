from eflycode import get_application_context


def main():
    """主函数，启动 Developer agent 的交互式会话"""
    
    # 获取应用程序上下文
    app_context = get_application_context()
    
    # 启动应用程序上下文（会自动初始化Environment和EventBus）
    app_context.start()
    
    # 使用AgentRegistry创建developer agent
    # agent_registry = app_context.get_agent_registry()
    # llm_engine = app_context.create_llm_engine()
    # developer = agent_registry.create_agent("developer", llm_engine)
    # run_loop = app_context.create_agent_run_loop(agent=developer, stream_output=True)
    # main_app = app_context.create_main_ui_app()
    
    # 严格按序启动：先初始化UI（完成订阅），再启动AgentRunLoop
    # main_app.initialize()  # 完成UI初始化和事件订阅
    # run_loop.start_in_background()  # 启动Agent运行循环（后台线程）
    
    # 启动主UI应用程序（主线程阻塞）
    # main_app.run()


if __name__ == "__main__":
    main()
