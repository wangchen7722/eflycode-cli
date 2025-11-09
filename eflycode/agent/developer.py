from typing import Optional

from eflycode.agent.core.agent import ConversationAgent
from eflycode.llm.llm_engine import LLMEngine
from eflycode.prompt import PromptLoader
from eflycode.tool import FILE_TOOL_GROUP


class Developer(ConversationAgent):
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
        tool_groups = [FILE_TOOL_GROUP]
        super().__init__(
            name=name,
            llm_engine=llm_engine,
            description=description,
            tools=[
                tool
                for group in tool_groups
                for tool in group.list_tools()
            ],
            **kwargs,
        )

    @property
    def system_prompt(self) -> str:
        """渲染系统提示词"""
        if self._system_prompt:
            return self._system_prompt
        return PromptLoader.get_instance().render_template(
            f"{self.role}/v1/system.prompt",
            name=self.name,
            role=self.role
        )
