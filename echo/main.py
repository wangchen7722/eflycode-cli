from echo.agents import Developer
from echo.llms import LLMConfig, OpenAIEngine
from echo.tools import ReadFileTool, CreateFileTool, EditFileTool, InsertFileTool, SearchFilesTool, ListFilesTool, \
    ExecuteCommandTool, ListCodeDefinitionsTool


def main():
    llm_config = LLMConfig(
        model="deepseek-chat",
        base_url="https://api.deepseek.com",
        api_key="sk-915afa73916e496fa8bcd002bb0c78aa",
        temperature=0.1
    )

    developer = Developer(
        name="developer",
        llm_engine=OpenAIEngine(llm_config),
        tools=[ReadFileTool(), EditFileTool(), InsertFileTool(), ExecuteCommandTool(), ListCodeDefinitionsTool(),
               CreateFileTool(), SearchFilesTool(), ListFilesTool()]
    )
    developer.run_loop()


if __name__ == "__main__":
    main()
