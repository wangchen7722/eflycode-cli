from typing import Optional, Sequence

from echoai.agents.agent import Agent, VectorDBConfig
from echoai.llms.llm_engine import LLMEngine
from echoai.tools import BaseTool


class DeepSearcher(Agent):
    """
    实现一个基于 Agentic RAG 的 DeepSearcher。
    """
    ROLE = "deepsearcher"
    DESCRIPTION = """
    一名技术精湛的软件开发者，精通多种编程语言、开发框架、设计模式以及最佳实践。
    """

    def __init__(
        self,
        llm_engine: LLMEngine,
        vector_db_config: Optional[VectorDBConfig] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tools: Optional[Sequence[BaseTool]] = None,
        **kwargs,
    ):
        super().__init__(
            name=name,
            llm_engine=llm_engine,
            vector_db_config=vector_db_config,
            description=description,
            tools=tools,
            **kwargs,
        )
