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