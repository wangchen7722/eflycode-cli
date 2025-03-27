from typing import Optional

from echoai.agents.agent import Agent, VectorDBConfig
from echoai.llms.llm_engine import LLMEngine
from echoai.tools import ReadFileTool, CreateFileTool, EditFileTool, InsertFileTool, SearchFilesTool, ListFilesTool, \
    ExecuteCommandTool, ListCodeDefinitionsTool, StoreMemoryTool


class Developer(Agent):
    ROLE = "developer"
    DESCRIPTION = """
    一名技术精湛的软件开发者，精通多种编程语言、开发框架、设计模式以及最佳实践。
    """

    def __init__(
        self,
        llm_engine: LLMEngine,
        vector_db_config: Optional[VectorDBConfig] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        **kwargs,
    ):
        developer_tools = [
            # 文件操作工具
            ReadFileTool(), CreateFileTool(), EditFileTool(), InsertFileTool(), SearchFilesTool(), ListFilesTool(),
            # 执行命令工具
            ExecuteCommandTool(),
            # 代码分析工具
            ListCodeDefinitionsTool()
        ]
        super().__init__(
            name=name,
            llm_engine=llm_engine,
            vector_db_config=vector_db_config,
            description=description,
            tools=developer_tools,
            **kwargs,
        )
