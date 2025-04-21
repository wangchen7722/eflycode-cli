from typing import Optional

from echoai.cli.tools.code_tool import ListCodeDefinitionsTool
from echoai.cli.tools.command_tool import ExecuteCommandTool
from echoai.cli.tools.file_tool import (
    CreateFileTool,
    EditFileTool,
    InsertFileTool,
    ListFilesTool,
    ReadFileTool,
    SearchFilesTool,
)
from echoai.core.agents.agent import Agent, VectorDBConfig
from echoai.core.llms.llm_engine import LLMEngine


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
