from typing import Optional

from echo.agent.core.agent import ConversationAgent, InteractiveConversationAgent
from echo.agent.registry import register_agent
from echo.llm.llm_engine import LLMEngine
from echo.tool import ReadFileTool, CreateFileTool, EditFileTool, SearchFilesTool, ListFilesTool, ExecuteCommandTool, ListCodeDefinitionsTool


@register_agent("developer")
class Developer(InteractiveConversationAgent):
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
            ReadFileTool(), CreateFileTool(), EditFileTool(), SearchFilesTool(), ListFilesTool(),
            # 执行命令工具
            ExecuteCommandTool(),
            # 代码分析工具
            # ListCodeDefinitionsTool()
        ]
        super().__init__(
            name=name,
            llm_engine=llm_engine,
            description=description,
            tools=developer_tools,
            **kwargs,
        )
