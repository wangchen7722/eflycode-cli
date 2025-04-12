from typing import Optional

from echoai.prompt.prompt_loader import PromptLoader
from echoai.mcp.mcp_hub import McpHub
from echoai.agents.agent import Agent, VectorDBConfig
from echoai.llms.llm_engine import LLMEngine
from echoai.tools.file_tool import ReadFileTool, CreateFileTool, EditFileTool, InsertFileTool, SearchFilesTool, ListFilesTool
from echoai.tools.mcp_tool import UseMcpTool

class McpAgent(Agent):
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
        mcp_agent_tools = [
            UseMcpTool(), 
            ReadFileTool(), CreateFileTool(), EditFileTool(), InsertFileTool(), SearchFilesTool(), ListFilesTool()
        ]
        super().__init__(
            name=name,
            llm_engine=llm_engine,
            vector_db_config=vector_db_config,
            description=description,
            tools=mcp_agent_tools,
            **kwargs,
        )
        
    def system_prompt(self):
        super_system_prompt = super().system_prompt()
        mcp_hub = McpHub.get_instance()
        mcp_connections = mcp_hub.list_connections()
        mcp_tools = {}
        mcp_tools = mcp_hub.list_tools()
        mcp_prompt = PromptLoader.get_instance().render_template(
            "partials/mcp.prompt",
            mcp_servers=mcp_connections,
            mcp_tools=mcp_tools,
        )
        return f"{super_system_prompt}\n{mcp_prompt}"

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from echoai.llms import LLMConfig, OpenAIEngine
    load_dotenv()
    llm_config = LLMConfig(
        model=os.environ["ECHO_MODEL"],
        base_url=os.environ["ECHO_BASE_URL"],
        api_key=os.environ["ECHO_API_KEY"],
        temperature=0.1
    )
    mcp_agent = McpAgent(llm_engine=OpenAIEngine(llm_config))
    
    mcp_hub = McpHub.get_instance()
    mcp_hub.launch_mcp_servers()
    mcp_agent.run_loop()
    mcp_hub.shutdown_mcp_servers()

    """
利用google搜索MCP相关文档，并保存到当前目录下的mcp_document.md中，我想要查询的文档内容是如何编写mcp服务，在你详细了解如何创建服务后再编写文档，你可以多次搜索和访问网页。你应该尽可能通过官方网站和文档来获取信息。并在获取信息后，继续搜索相关内容，以获得更加完整且详细的文档，包括详细的概念介绍、解释以及对应的示例代码，文档应该尽可能详细，最后再将其保存到mcp_document.md中。
    """
    