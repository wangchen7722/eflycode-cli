import asyncio
import aiohttp
from enum import Enum as PyEnum
from typing import Dict, Any, Optional
from pydantic import BaseModel
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.client.websocket import websocket_client

class McpClient(BaseModel):
    """MCP Client wrapper."""

    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack: AsyncExitStack = AsyncExitStack()
        self._read_stream: Optional[asyncio.StreamReader] = None

    async def connect(self, server_script_path: str):
        """Connect to the MCP server.
        
        Args:
            server_script_path (str): Path to the MCP server script.
        """
        is_python = server_script_path.endswith(".py")
        is_js = server_script_path.endswith(".js")
        if not (is_python or is_js):
            raise ValueError("Server script must be a Python or JavaScript file.")
        
        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.read_stream, self.write_stream = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(
            self.read_stream, self.write_stream
        ))
        await self.session.initialize()

        # setup prompts, tools, resources, etc.


class McpServerStatus(PyEnum):
    """Enum for MCP server status."""
    CONNECTING: str = "connecting"
    CONNECTED: str = "connected"
    DISCONNECTED: str = "disconnected"

class McpServer(BaseModel):
    name: str
    config: Dict[str, Any]
    status: McpServerStatus

class McpConnection:
    server: McpServer
    client: McpClient