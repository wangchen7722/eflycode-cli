import os
from echo.agents.agent import AgentCapability
from echo.agents.developer import Developer
from echo.llms.llm_engine import LLMConfig
from echo.llms.openai_engine import OpenAIEngine
from echo.tools import ReadFileTool, CreateFileTool, UpdateFileTool, SearchFilesTool, ListFilesTool, ExecuteCommandTool, ListCodeDefinitionsTool

# llm_config = LLMConfig(
#     model=os.environ["ECHO_MODEL"],
#     base_url=os.environ["ECHO_BASE_URL"],
#     api_key=os.environ["ECHO_API_KEY"],
#     temperature=0.1
# )
llm_config = LLMConfig(
    model="ep-20250220154917-m5tv5",
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key="cb7cb751-3de9-4e2b-89bb-bbd7a303f193",
    temperature=0.1
)
developer = Developer(
    name="developer",
    llm_engine=OpenAIEngine(llm_config),
    capabilities=[AgentCapability.USE_TOOL],
    tools=[ReadFileTool(), UpdateFileTool(), ExecuteCommandTool(), ListCodeDefinitionsTool(), CreateFileTool(), SearchFilesTool(), ListFilesTool()]
)
developer.run_loop()
# print(developer.system_prompt())
