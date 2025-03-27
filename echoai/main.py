import os

from dotenv import load_dotenv

from echoai.agents import Developer
from echoai.llms import LLMConfig, OpenAIEngine
from echoai.tools import ReadFileTool, CreateFileTool, EditFileTool, InsertFileTool, SearchFilesTool, ListFilesTool, \
    ExecuteCommandTool, ListCodeDefinitionsTool

load_dotenv()


def main():
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
               CreateFileTool(), SearchFilesTool(), ListFilesTool()]
    )
    developer.run_loop()


if __name__ == "__main__":
    main()
