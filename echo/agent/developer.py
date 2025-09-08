from typing import Optional

from echo.agent.core.agent import InteractiveConversationAgent
from echo.agent.registry import register_agent
from echo.llm.llm_engine import LLMEngine
from echo.prompt import PromptLoader
from echo.tool import FILE_TOOL_GROUP, ExecuteCommandTool, ListCodeDefinitionsTool
from echo.util.system import get_system_info


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
            *FILE_TOOL_GROUP,
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

    @property
    def system_prompt(self) -> str:
        """渲染系统提示词"""
        if self._system_prompt:
            return self._system_prompt
        system_info = get_system_info()
        return PromptLoader.get_instance().render_template(
            f"{self.role}/v1/system.prompt",
            name=self.name,
            role=self.role,
            tools=self._tool_map,
            system_info=system_info,
            stream_parser=self.stream_parser,
        )

