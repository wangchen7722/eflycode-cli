from typing import Literal, Optional, List, Dict
from pydantic import BaseModel, Field

class BaseServerConfig(BaseModel):
    """Base configuration for the MCP server."""
    name: Optional[str] = Field(None, description="Name of the MCP server.")
    description: Optional[str] = Field(None, description="Description of the MCP server.")

class StdioServerConfig(BaseServerConfig):
    """Configuration for the Stdio MCP server."""
    type: Literal["stdio"] = "stdio"
    command: str = Field(..., description="Command to run the MCP server.")
    args: Optional[List[str]] = Field(None, description="Arguments to run the MCP server.")
    env: Optional[Dict[str, str]] = Field(None, description="Environment variables to run the MCP server.")

class SSEServerConfig(BaseServerConfig):
    """Configuration for the SSE MCP server."""
    type: Literal["sse"] = "sse"
    url: str = Field(..., description="URL of the SSE MCP server.")
    headers: Optional[Dict[str, str]] = Field(None, description="Headers to send to the SSE MCP server.")

class WebsocketServerConfig(BaseServerConfig):
    """Configuration for the Websocket MCP server."""
    type: Literal["websocket"] = "websocket"
    url: str = Field(..., description="URL of the Websocket MCP server.")

class MCPServerSetting(BaseModel):
    """Configuration for the MCP server."""
    mcpServers: Dict[str, BaseServerConfig] = Field(..., description="Configuration for the MCP servers.")
