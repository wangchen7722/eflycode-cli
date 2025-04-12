import json
from unittest import result

import anyio
import jsonschema

from echoai.services.mcp.mcp_hub import McpHub, launch_mcp_servers, is_mcp_server_initialized
from echoai.tools.base_tool import BaseTool
from echoai.utils.logger import get_logger

logger = get_logger()

mcp_hub = McpHub.get_instance()

if not is_mcp_server_initialized():
    logger.warning("MCP servers not initialized, launch mcp servers automatically.")
    launch_mcp_servers()

class UseMcpTool(BaseTool):
    NAME = "use_mcp_tool"
    TYPE = "function"
    IS_APPROVAL = True
    DESCRIPTION = """
    Request to use a tool provided by a connected MCP server. Each MCP server can provide multiple tools with different capabilities. Tools have defined input schemas that specify required and optional parameters.
    """
    DISPLAY = "{agent_name} want to use mcp tool"
    PARAMETERS = {
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
        }
    }
    EXAMPLES = {
        "Request to use weather tool provided by weather MCP server": {
            "server_name": "weather",
            "tool_name": "get_weather",
            "arguments": {
                "city": "Shanghai",
                "date": "2023-03-20"
            }
        }
    }
    
    async def _a_do_run(self, server_name: str, tool_name: str, arguments: str):
        """Use a tool provided by a connected MCP server.

        Args:
            server_name: The name of the MCP server that provides the tool.
            tool_name: The name of the tool to be used.
            arguments: A JSON object containing the tool's input parameters,, following the tool's input schema.
        """ 
        mcp_connection = await mcp_hub.get_mcp_connection(server_name)
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
            result = await mcp_connection.call_tool(tool_name, json_data)
            return result
        except Exception as e:
            return f"Failed to call tool {tool_name} in server {server_name}: {e}"
    
    def do_run(self, server_name: str, tool_name: str, arguments: str):
        """Use a tool provided by a connected MCP server.

        Args:
            server_name: The name of the MCP server that provides the tool.
            tool_name: The name of the tool to be used.
            arguments: A JSON object containing the tool's input parameters,, following the tool's input schema.
        """
        return anyio.run(self._a_do_run, server_name, tool_name, arguments)
       
        
if __name__ == "__main__":
    tool = UseMcpTool()
    result = tool.do_run("filesystem", "list_directory", '{"path": "/home/wangchen/projects/Roo-Code"}')
    print(result)