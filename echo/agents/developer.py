import json
from typing import Optional, Sequence

from echo.agents.agent import Agent, AgentCapability, VectorDBConfig
from echo.llms.llm_engine import LLMEngine
from echo.tools import BaseTool


class Developer(Agent):
    ROLE = "developer"
    DESCRIPTION = """
    a highly skilled software developer with extensive knowledge in many programming languages, frameworks, design patterns, and best practices.
    """

    def __init__(
            self,
            llm_engine: LLMEngine,
            vector_db_config: Optional[VectorDBConfig] = None,
            capabilities: Optional[Sequence[AgentCapability]] = None,
            name: Optional[str] = None,
            description: Optional[str] = None,
            tools: Optional[Sequence[BaseTool]] = None,
            **kwargs,
    ):
        super().__init__(
            name=name,
            llm_engine=llm_engine,
            vector_db_config=vector_db_config,
            capabilities=capabilities,
            description=description,
            tools=tools,
            **kwargs,
        )

    def run_loop(self):
        from echo.ui.console import ConsoleUI
        console = ConsoleUI.get_instance()
        enable_stream = True
        user_input = None
        console.show_text(f"Hello, {self.name}!")
        while True:
            if user_input is None:
                user_input = console.acquire_user_input()
            if user_input.strip() == "exit" or user_input.strip() == "quit":
                break
            agent_response = self.run(user_input, stream=enable_stream)
            user_input = None
            console.show_text(f"{self.name}: ", end="")
            if enable_stream:
                for chunk in agent_response:
                    if chunk.tool_calls:
                        user_input = ""
                        for tool_call in chunk.tool_calls:
                            # 换行
                            console.show_text("")
                            tool_call_name = tool_call["function"]["name"]
                            tool_call_arguments = json.loads(tool_call["function"]["arguments"])
                            tool_call_arguments_str = "\n".join([f"{k}={v}" for k, v in tool_call_arguments.items()])
                            with console.create_loading(tool_call_name):
                                tool_call_result = self.execute_tool(tool_call)
                            tool_call_panel_str = "Arguments:\n{}\nResult:\n{}".format(tool_call_arguments_str, tool_call_result)
                            user_input += tool_call_result + "\n"
                            console.show_panel([self.name, tool_call_name], tool_call_panel_str)
                    else:
                        if not chunk.content:
                            continue
                        console.show_text(chunk.content, end="")
            # 换行
            console.show_text("")