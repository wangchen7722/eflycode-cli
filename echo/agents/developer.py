from typing import Optional

from echo.tools.code_tool import ListCodeDefinitionsTool
from echo.tools.command_tool import ExecuteCommandTool
from echo.tools.file_tool import (
    CreateFileTool,
    EditFileTool,
    InsertFileTool,
    ListFilesTool,
    ReadFileTool,
    SearchFilesTool,
)
from echo.agents.agent import Agent
from echo.llms.llm_engine import LLMEngine


class Developer(Agent):
    ROLE = "developer"
    DESCRIPTION = """
    一名技术精湛的软件开发者，精通多种编程语言、开发框架、设计模式以及最佳实践。
    """

    def __init__(
        self,
        llm_engine: LLMEngine,
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
            description=description,
            tools=developer_tools,
            **kwargs,
        )
