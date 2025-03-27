import os

from dotenv import load_dotenv

from echoai.agents import Developer
from echoai.llms import LLMConfig
from echoai.llms import OpenAIEngine
from echoai.tools import ReadFileTool, CreateFileTool, EditFileTool, InsertFileTool, SearchFilesTool, ListFilesTool, \
    ExecuteCommandTool, ListCodeDefinitionsTool, StoreMemoryTool

load_dotenv()

llm_config = LLMConfig(
    model=os.environ["ECHO_MODEL"],
    base_url=os.environ["ECHO_BASE_URL"],
    api_key=os.environ["ECHO_API_KEY"],
    temperature=0.1
)

developer = Developer(
    name="developer",
    llm_engine=OpenAIEngine(llm_config),
    tools=[ReadFileTool(), EditFileTool(), InsertFileTool(), ExecuteCommandTool(), ListCodeDefinitionsTool(),
           CreateFileTool(), SearchFilesTool(), ListFilesTool(), StoreMemoryTool(), ]
)
developer.run_loop()
# print(developer.system_prompt())
