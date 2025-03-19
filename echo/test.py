import os

from echo.llms.llm_engine import LLMConfig
from echo.llms.openai_engine import OpenAIEngine
from echo.agents.agent import Agent, AgentCapability
from echo.tools.file_tool import ReadFileTool


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
        tools=[ReadFileTool()]
    )

    # 测试同步响应
    # message = "请帮我查看文件/path/to/demo.txt的内容"
    # response_without_stream = agent.run(message, stream=False)
    # print(response_without_stream.content)
    # print(response_without_stream)
    print("================================================")

    # 测试流式响应
    message = "请帮我查看文件/path/to/demo.txt的内容"
    response_with_stream = agent.run(message, stream=True)
    for agent_response_chunk in response_with_stream.stream():
        print(agent_response_chunk)
    print(response_with_stream)


if __name__ == "__main__":
    test_agent_run()
