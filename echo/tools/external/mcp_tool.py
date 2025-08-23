import json

import jsonschema

from echo.mcp.mcp_hub import McpHub
from echo.utils.logger import get_logger
from echo.tools.base_tool import BaseTool

logger = get_logger()

class UseMcpTool(BaseTool):
    
    def _get_mcp_hub(self) -> McpHub:
        """获取MCP Hub实例，如果未初始化则进行延迟初始化"""
        mcp_hub = McpHub.get_instance()
        
        if not mcp_hub.is_initialized:
            logger.warning("MCP servers not initialized, launch mcp servers automatically.")
            mcp_hub.launch_mcp_servers()
            
        return mcp_hub
    
    @property
    def name(self) -> str:
        return "use_mcp_tool"
    
    @property
    def type(self) -> str:
        return "function"
    
    @property
    def is_approval(self) -> bool:
        return False
    
    @property
    def description(self) -> str:
        return """
    Request to use a tool provided by a connected MCP server. Each MCP server can provide multiple tools with different capabilities. Tools have defined input schemas that specify required and optional parameters.
    """
    
    def display(self, **kwargs) -> str:
        return "使用MCP工具"
    
    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "server_name": {
                    "type": "string",
                    "description": "The name of the MCP server that provides the tool."
                },
                "tool_name": {
                    "type": "string",
                    "description": "The name of the tool to be used."
                },
                "arguments": {
                    "type": "string",
                    "description": "A JSON object containing the tool's input parameters, , following the tool's input schema."
                }
            },
            "required": ["server_name", "tool_name", "arguments"],
        }
    @property
    def examples(self):
        return {
            "Request to use weather tool provided by weather MCP server": {
                "type": self.type,
                "name": self.name,
                "arguments": {
                    "server_name": "weather",
                    "tool_name": "get_weather",
                    "arguments": "{\"city\": \"Shanghai\", \"date\": \"2023-03-20\"}"
                }
            }
        }
    
    def do_run(self, server_name: str, tool_name: str, arguments: str):
        """Use a tool provided by a connected MCP server.

        Args:
            server_name: The name of the MCP server that provides the tool.
            tool_name: The name of the tool to be used.
            arguments: A JSON object containing the tool's input parameters,, following the tool's input schema.
        """
        mcp_hub = self._get_mcp_hub()
        mcp_connection = mcp_hub.get_mcp_connection(server_name)
        if mcp_connection is None:
            avaliable_connections = mcp_hub.list_connections()
            return f"No MCP connection found for server {server_name}, avaliable connections: {avaliable_connections}"
        tool_schema = mcp_connection.get_tool(tool_name)
        if tool_schema is None:
            available_tools = [
                tool_name for tool_name, tool_schema in mcp_connection.tools
            ]
            return f"Tool {tool_name} not found in server {server_name}, available tools: {available_tools}"
        try:
            json_data = json.loads(arguments)
        except json.JSONDecodeError:
            return f"Invalid JSON format for arguments: {arguments}"
        try:
            jsonschema.validate(json_data, tool_schema["function"]["parameters"])
        except jsonschema.ValidationError as e:
            return f"Invalid arguments: {e.message}, parameter schema: {tool_schema['function']['parameters']}"
        try:
            result = mcp_connection.call_tool_sync(tool_name, json_data)
            if result.isError:
                return f"Failed to call tool {tool_name} in server {server_name}: {result.content}"
            return f"Tool {tool_name} in server {server_name} called successfully, result: {result.content}"
        except Exception as e:
            return f"Failed to call tool {tool_name} in server {server_name}: {e}"
    
if __name__ == "__main__":
    tool = UseMcpTool()
    tool_result = tool.run("filesystem", "list_directory", '{"path": "/root/projects/Roo-Code"}')
    print(tool_result)