from echo.config import GlobalConfig
from echo.llm.openai_engine import OpenAIEngine
from echo.agent.developer import Developer
from echo.agent.run_loop import AgentRunLoop
from echo.ui.console import ConsoleUI


def main():
    """主函数，启动 Developer agent 的交互式会话"""
    
    # 获取全局配置
    global_config = GlobalConfig.get_instance()
    
    # 创建 LLM 引擎
    llm_engine = OpenAIEngine(
        llm_config=global_config.get_default_llm_config(), 
        advisors=["buildin_environment_advisor", "buildin_tool_call_advisor"]
    )
    
    # 创建 Developer agent
    developer = Developer(llm_engine=llm_engine)
    
    # 创建控制台 UI
    ui = ConsoleUI()
    
    # 创建运行循环
    run_loop = AgentRunLoop(
        agent=developer,
        ui=ui,
        welcome_message="欢迎使用 EchoAI Developer Agent！输入 /help 查看可用命令。",
        stream_output=True
    )
    
    # 启动运行循环
    run_loop.run()


if __name__ == "__main__":
    main()
