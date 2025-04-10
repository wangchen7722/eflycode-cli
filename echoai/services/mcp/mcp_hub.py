import asyncio
import json
import logging
from contextlib import AsyncExitStack
from pathlib import Path
from enum import Enum as PyEnum
from typing import Any, Dict, Optional, Union, List, Tuple, Self

import mcp.types as mcp_types
from pydantic import BaseModel, Field
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.websocket import websocket_client

from echoai.utils.logger import get_logger
from echoai.services.mcp.schema import (
    BaseServerConfig,
    SSEServerConfig,
    StdioServerConfig,
    WebsocketServerConfig,
    MCPServerSetting,
)

logger: logging.Logger = get_logger(log_level=logging.DEBUG)


class McpClient:
    """MCP Client wrapper."""

    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack: AsyncExitStack = AsyncExitStack()
        
        self.prompts: List[mcp_types.Prompt] = []
        self.tools: List[mcp_types.Tool] = []
        self.resources: List[mcp_types.Resource] = []

    async def connect_to_server(
        self,
        config: Union[StdioServerConfig, SSEServerConfig, WebsocketServerConfig],
    ):
        """Connect to the MCP server.
        Args:
            config (Union[StdioServerConfig, SSEServerConfig, WebsocketServerConfig]): Configuration for the MCP server.
        """
        if config.type == "stdio":
            await self.connect_to_stdio_server(config)
        elif config.type == "sse":
            await self.connect_to_sse_server(config)
        elif config.type == "websocket":
            await self.connect_to_websocket_server(config)
        else:
            raise ValueError("Unknown MCP server type.")

    async def connect_to_stdio_server(self, config: StdioServerConfig):
        """Connect to the MCP server.
        Args:
            config (StdioServerConfig): Configuration for the MCP server.
        """
        server_params = StdioServerParameters(
            command=config.command, args=config.args, env=config.env
        )
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read_stream, write_stream = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )

        await self.session.initialize()
        self.prompts = await self.session.list_prompts()
        self.tools = await self.session.list_tools()
        self.resources = await self.session.list_resources()
        
    async def connect_to_sse_server(self, config: SSEServerConfig):
        """Connect to the MCP server.
        Args:
            config (SSEServerConfig): Configuration for the MCP server.
        """
        raise NotImplementedError()

    async def connect_to_websocket_server(self, config: WebsocketServerConfig):
        """Connect to the MCP server.
        Args:
            config (WebsocketServerConfig): Configuration for the MCP server.
        """
        raise NotImplementedError()
    
    async def call_tool(self, name: str, arguments: dict) -> mcp_types.CallToolResult:
        """Call a tool."""
        return await self.session.call_tool(name, arguments)
    
    async def read_resource(self, uri: str) -> mcp_types.ReadResourceResult:
        """Read a resource."""
        return await self.session.read_resource(uri)

    async def aclose(self):
        """Close the MCP client."""
        await self.exit_stack.aclose()
        self.session = None
        self.prompts = []
        self.tools = []
        self.resources = []


class McpServerStatus(PyEnum):
    """Enum for MCP server status."""

    CONNECTING: str = "connecting"
    CONNECTED: str = "connected"
    DISCONNECTED: str = "disconnected"


class McpConnection:
    """MCP Connection."""

    def __init__(
        self,
        name: str,
        config: Union[StdioServerConfig, SSEServerConfig, WebsocketServerConfig],
    ):
        """Initialize the MCP manager.
        Args:
            name (str): Server name.
            config (Union[StdioServerConfig, SSEServerConfig, WebsocketServerConfig]): Server configuration.
        """
        self.name = name
        self.config = config
        self.status = McpServerStatus.CONNECTING
        self.error: str = ""

        self.client: Optional[McpClient] = None

    async def astart(self):
        self.client = McpClient()
        self.status = McpServerStatus.CONNECTING
        try:
            await self.client.connect_to_server(self.config)
            self.status = McpServerStatus.CONNECTED
        except Exception as e:
            self.error = str(e)
            logger.error(f"Failed to connect to server {self.name}: {e}")
            self.status = McpServerStatus.DISCONNECTED

    async def aclose(self):
        """Close the MCP client."""
        await self.client.aclose()
        self.client = None
        self.status = McpServerStatus.DISCONNECTED
        
    def tools(self) -> List[mcp_types.Tool]:
        """Get all tools."""
        return self.client.tools
    
    def resources(self) -> List[mcp_types.Resource]:
        """Get all resources."""
        return self.client.resources
    
    def prompts(self) -> List[mcp_types.Prompt]:
        """Get all prompts."""
        return self.client.prompts
        
        

class McpHub:
    """MCP Manager."""

    connections: List[McpConnection] = []
    _instance: "McpHub" = None

    def __init__(self) -> None:
        """Initialize the MCP manager."""
        self._lock = asyncio.Lock()
        # self.initialize_mcp_servers()
        
    def __new__(cls) -> Self:
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_mcp_setting_filepath(self):
        """Get the MCP setting filepath."""
        # 当前项目的根目录
        project_root = Path(__file__).parent.parent.parent.parent
        mcp_setting_filepath = project_root / "echoai_mcp_setting.json"
        if not mcp_setting_filepath.exists():
            with open(mcp_setting_filepath, "w") as f:
                f.write(json.dumps({"mcpServers": {}}, ensure_ascii=False))
        return mcp_setting_filepath

    def validate_mcp_setting(self, mcp_setting: Dict[str, Any]) -> MCPServerSetting:
        """Validate the MCP setting."""
        validated_mcp_setting = {}
        if "mcpServers" not in mcp_setting:
            return False, validated_mcp_setting
        # 验证 mcpServers 字段
        if not isinstance(mcp_setting["mcpServers"], dict):
            return False, {}
        validated_mcp_setting["mcpServers"] = {}
        # 验证 mcpServers 字段中的每个子字段
        for server_name, server_config in mcp_setting["mcpServers"].items():
            if "type" not in server_config:
                server_config["type"] = "stdio"
            if server_config["type"] == "stdio":
                server_config_obj = StdioServerConfig.model_validate(server_config)
            elif server_config["type"] == "sse":
                server_config_obj = SSEServerConfig.model_validate(server_config)
            elif server_config["type"] == "websocket":
                server_config_obj = WebsocketServerConfig.model_validate(server_config)
            else:
                raise ValueError("Unknown MCP server type.")
            validated_mcp_setting["mcpServers"][server_name] = server_config_obj
        return MCPServerSetting.model_validate(validated_mcp_setting)

    async def initialize_mcp_servers(self):
        """Initialize all MCP connections."""
        logger.info("initialize mcp servers...")
        mcp_setting_filepath = self.get_mcp_setting_filepath()
        try:
            with open(mcp_setting_filepath, "r") as f:
                mcp_setting = json.loads(f.read())
        except Exception as e:
            logger.error(f"Error reading MCP setting file: {e}")
            return
        try:
            mcp_server_setting = self.validate_mcp_setting(mcp_setting)
        except Exception as e:
            logger.error(f"Error validating MCP setting: {e}")
            return
        try:
            await self.update_mcp_connections(mcp_server_setting)
        except Exception as e:
            logger.error(f"Error updating MCP connections: {e}")
            return
        logger.info("mcp servers initialized.")
        
    async def get_mcp_connection(self, server_name: str) -> Optional[McpConnection]:
        """Get a MCP connection."""
        await self._lock.acquire()
        connection = None
        for conn in self.connections:
            if conn.name == server_name:
                connection = conn
                break
        self._lock.release()
        return connection

    async def _add_mcp_connection(
        self,
        name: str,
        config: Union[StdioServerConfig, SSEServerConfig, WebsocketServerConfig],
    ):
        mcp_connection = McpConnection(name=name, config=config)
        await mcp_connection.astart()
        self.connections.append(mcp_connection)

    async def update_mcp_connections(self, mcp_server_setting: MCPServerSetting):
        """Update all MCP connections."""
        await self._lock.acquire()
        currnet_server_names = [connection.name for connection in self.connections]
        new_server_names = [
            server_name for server_name in mcp_server_setting.mcpServers.keys()
        ]
        # 删除连接
        for server_name in currnet_server_names:
            if server_name not in new_server_names:
                await self._remove_mcp_connection(server_name)
                logger.info(f"Removed MCP connection {server_name}")
        # 添加或更新连接
        for server_name, server_config in mcp_server_setting.mcpServers.items():
            if server_name in currnet_server_names:
                await self._remove_mcp_connection(server_name)
                await self._add_mcp_connection(server_name, server_config)
                logger.info(f"Updated MCP connection {server_name}")
            else:
                await self._add_mcp_connection(server_name, server_config)
                logger.info(f"Added MCP connection {server_name}")
        self._lock.release()

    async def _remove_mcp_connection(self, server_name: str):
        """Remove a MCP connection."""
        connection = await self.get_mcp_connection(server_name)
        if connection:
            await connection.aclose()
            self.connections.remove(connection)            

    async def remove_all_connections(self):
        """Close all MCP connections."""
        await self._lock.acquire()
        for connection in self.connections:
            try:
                await connection.aclose()
            except Exception as e:
                logger.error(f"Error closing connection {connection.name}: {e}")
        self.connections = []
        self._lock.release()


if __name__ == "__main__":

    async def async_main():
        mcp_hub = McpHub()
        await mcp_hub.initialize_mcp_servers()
        while True:
            user_input = input("Enter command: ")
            if user_input == "list":
                for connection in mcp_hub.connections:
                    print(f"{connection.name}: {connection.status}")
            if user_input == "tools":
                ...
            if user_input == "exit":
                break
        await mcp_hub.remove_all_connections()

    asyncio.run(async_main())
