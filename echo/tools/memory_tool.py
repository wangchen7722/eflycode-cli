from echo.memory import AgentMemory, MemoryType
from echo.tools.base_tool import BaseTool, ToolType


class StoreMemoryTool(BaseTool):
    """
    用于存储和管理记忆的工具。
    """

    NAME = "store_memory"
    TYPE = ToolType.MEMORY
    DESCRIPTION = """
    Request to store a memory about the user's preferences, coding habits, instructions and project's context.
    This tool should be used to remember information such as naming conventions, preferred code styles, commonly used patterns, specific user requirements or project's context. 
    The stored memory will be used to guide future decisions, ensure consistency with the user's expectations, and personalize the agent's behavior over time. 
    Use this tool when you encounter recurring behaviors, preferences, explicit user instructions and project's context that should be remembered long-term.
    """
    PARAMETERS = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "A brief title or category for the content. such as 'naming convention', 'code style' 'user preference' or 'project context'.",
            },
            "content": {
                "type": "string",
                "description": "The actual memory content to store, such as a rule, pattern, habit, user requirement or project's context.",
            },
        },
        "required": ["topic", "content"],
    }
    EXAMPLES = {
        "Request to Storing a naming convention": {
            "type": TYPE,
            "name": NAME,
            "arguments": {
                "topic": "naming convention",
                "content": "Use CamelCase for class names, snake_case for function names, and UPPER_CASE for constants."
            }
        },
    }

    def do_run(self, memory: AgentMemory, topic: str, content: str) -> str:
        """
        存储记忆。
        """
        try:
            memory_item = memory.store_memory(
                content=content,
                memory_type=MemoryType.LONG_TERM,
                metadata={"topic": topic},
            )
            return "Memory stored successfully. "
        except Exception as e:
            return f"Failed to store memory: {e}"


