from typing import Annotated

from eflycode.core.llm.protocol import ToolFunctionParameters
from eflycode.core.tool.base import BaseTool, ToolType


class FinishTaskTool(BaseTool):
    """完成任务工具

    当模型完成对用户问题的回答或任务总结时，调用此工具来结束任务。
    工具会流式输出 content 参数的内容，而不是显示工具调用信息。
    """

    @property
    def name(self) -> str:
        return "finish_task"

    @property
    def type(self) -> str:
        return ToolType.FUNCTION

    @property
    def permission(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return (
            "完成任务工具。当模型完成对用户问题的回答或任务总结时，调用此工具来结束任务。"
            "调用此工具后，任务将结束，工具会流式输出 content 参数的内容。"
            "此工具应该用于：1) 对用户提问进行最终回答；2) 对已完成的任务进行总结。"
        )

    @property
    def parameters(self) -> ToolFunctionParameters:
        return ToolFunctionParameters(
            type="object",
            properties={
                "content": {
                    "type": "string",
                    "description": "任务的最终回答或总结内容，将流式输出给用户",
                },
            },
            required=["content"],
        )

    def do_run(self, content: Annotated[str, "任务的最终回答或总结内容"]) -> str:
        """执行完成任务工具

        Args:
            content: 任务的最终回答或总结内容

        Returns:
            str: 空字符串，因为内容会通过事件流式输出
        """
        # 内容会通过事件系统流式输出，这里返回空字符串
        return ""

