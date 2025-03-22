import os
from echo.agents.agent import AgentCapability
from echo.agents.developer import Developer
from echo.llms.llm_engine import LLMConfig
from echo.llms.openai_engine import OpenAIEngine
from echo.tools import ReadFileTool, EditFileWithReplace, ExecuteCommandTool

llm_config = LLMConfig(
    model=os.environ["ECHO_MODEL"],
    base_url=os.environ["ECHO_BASE_URL"],
    api_key=os.environ["ECHO_API_KEY"],
    temperature=0.1
)
developer = Developer(
    name="developer",
    llm_engine=OpenAIEngine(llm_config),
    capabilities=[AgentCapability.USE_TOOL],
    tools=[ReadFileTool(), EditFileWithReplace(), ExecuteCommandTool()]
)
developer.run_loop()
# print(developer.system_prompt())
