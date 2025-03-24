import os
from echo.agents import Developer
from echo.llms import LLMConfig
from echo.llms import OpenAIEngine
from echo.tools import ReadFileTool, CreateFileTool, EditFileTool, InsertFileTool, SearchFilesTool, ListFilesTool, ExecuteCommandTool, ListCodeDefinitionsTool

# llm_config = LLMConfig(
#     model=os.environ["ECHO_MODEL"],
#     base_url=os.environ["ECHO_BASE_URL"],
#     api_key=os.environ["ECHO_API_KEY"],
#     temperature=0.1
# )

llm_config = LLMConfig(
    # model="ep-20250220154917-m5tv5",
    model="ep-20250220155009-8ckjl",
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key="cb7cb751-3de9-4e2b-89bb-bbd7a303f193",
    temperature=0.1
)

# llm_config = LLMConfig(
#     model="gemini-1.5-pro",
#     base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
#     api_key="AIzaSyAdKrKLqRnK7-kzLjZcw5U3ZbOD10f-hAA",
#     temperature=0.1
# )

developer = Developer(
    name="developer",
    llm_engine=OpenAIEngine(llm_config),
    tools=[ReadFileTool(), EditFileTool(), InsertFileTool(), ExecuteCommandTool(), ListCodeDefinitionsTool(), CreateFileTool(), SearchFilesTool(), ListFilesTool()]
)
developer.run_loop()
# print(developer.system_prompt())
