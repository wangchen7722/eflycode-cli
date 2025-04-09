import asyncio
import logging
from contextlib import AsyncExitStack
from enum import Enum as PyEnum
from typing import Any, Dict, Optional, Union, List

from pydantic import BaseModel, Field
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.websocket import websocket_client

from echoai.utils.logger import get_logger
from echoai.services.mcp.schema import (
    SSEServerConfig,
    StdioServerConfig,
    WebsocketServerConfig,
)

logger: logging.Logger = get_logger(log_level=logging.DEBUG)


class McpClient:
    """MCP Client wrapper."""

    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack: AsyncExitStack = AsyncExitStack()

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

    async def aclose(self):
        """Close the MCP client."""
        await self.exit_stack.aclose()


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


class McpHub:
    """MCP Manager."""
    connections: List[McpConnection] = []

    async def connect_to_server(
        self,
        name: str,
        config: Union[StdioServerConfig, SSEServerConfig, WebsocketServerConfig],
    ):
        mcp_connection = McpConnection(name=name, config=config)
        await mcp_connection.astart()
        self.connections.append(mcp_connection)
        
    async def aclose_all(self):
        """Close all MCP connections."""
        for connection in self.connections:
            try:
                await connection.aclose()
            except Exception as e:
                logger.error(f"Error closing connection {connection.name}: {e}")
        self.connections = []

if __name__ == "__main__":
    async def async_main():
        mcp_hub = McpHub()
        server_configs = {
            "mcpServers": {
                "weather": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "@modelcontextprotocol/server-filesystem",
                        "/root/projects/Roo-Code"
                    ]
                }
            }
        }
        for server_name, server_config in server_configs["mcpServers"].items():
            await mcp_hub.connect_to_server(
                name=server_name, config=StdioServerConfig(**server_config)
            )
            break
        while True:
            user_input = input("Enter command: ")
            if user_input == "exit":
                break
        await mcp_hub.aclose_all()
    asyncio.run(async_main())
