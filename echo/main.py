from echo.agents import Developer
from echo.llms import LLMConfig, OpenAIEngine
from echo.tools import ReadFileTool, CreateFileTool, EditFileTool, InsertFileTool, SearchFilesTool, ListFilesTool, \
    ExecuteCommandTool, ListCodeDefinitionsTool


def main():
    llm_config = LLMConfig(
        # model="ep-20250220154917-m5tv5",
        model="ep-20250220155009-8ckjl",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        api_key="cb7cb751-3de9-4e2b-89bb-bbd7a303f193",
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
