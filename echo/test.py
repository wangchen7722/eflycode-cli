import os
from typing import Generator

from echo.llms.llm_engine import LLMConfig
from echo.llms.openai_engine import OpenAIEngine
from echo.agents.agent import Agent, AgentCapability, AgentResponse


def test_agent_run():
    # 初始化LLM引擎
    llm_config = LLMConfig(
        model=os.environ["ECHO_MODEL"],
        base_url=os.environ["ECHO_BASE_URL"],
        api_key=os.environ["ECHO_API_KEY"],
        temperature=0.7,
        max_tokens=100
    )
    llm_engine = OpenAIEngine(llm_config)

    # 初始化Agent
    agent = Agent(
        name="测试助手",
        llm_engine=llm_engine,
        capabilities=[AgentCapability.USE_TOOL],
        description="这是一个测试用的智能助手",
    )

    # 测试同步响应
    message = "你好，请介绍一下你自己"
    response: Generator[AgentResponse, None, None] = agent.run(message)
    for agent_response in response:
        if agent_response.finish_reason == "error":
            print(f"错误：{agent_response.content}")
        else:
            print(f"助手：{agent_response.content}")
            print(f"Token使用：{agent_response.total_tokens}")

    # 测试流式响应
    try:
        message = "请给我讲个故事"
        response: Generator[AgentResponse, None, None] = agent.run(message)
        for agent_response in response:
            if agent_response.finish_reason == "error":
                print(f"错误：{agent_response.content}")
            else:
                print("助手：", end="", flush=True)
                for chunk in agent_response.stream():
                    print(chunk, end="", flush=True)
                print(f"\nToken使用：{agent_response.total_tokens}")
    except Exception as e:
        print(f"发生错误：{str(e)}")


if __name__ == "__main__":
    test_agent_run()
