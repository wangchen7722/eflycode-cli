import asyncio
from contextlib import AsyncExitStack
from enum import Enum as PyEnum
import json
import logging
from pathlib import Path
import threading
import traceback
from typing import Any, Dict, List, Optional, Self, Union

from anyio import create_task_group
from anyio.abc import TaskGroup
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.websocket import websocket_client
import mcp.types as mcp_types

from echoai.services.mcp.schema import (
    MCPServerSetting,
    SSEServerConfig,
    StdioServerConfig,
    WebsocketServerConfig,
)
from echoai.tools.schema import ToolSchema
from echoai.utils.logger import get_logger

logger: logging.Logger = get_logger(log_level=logging.DEBUG)


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
        self.server_info = {}

        self.tools: List[ToolSchema] = []
        self.prompts: List[mcp_types.Prompt] = []
        self.resources: List[mcp_types.Resource] = []

        self._session: Optional[ClientSession] = None
        self._initialize_event: asyncio.Event = asyncio.Event()
        self._shutdown_event: asyncio.Event = asyncio.Event()
        self._exit_stack: AsyncExitStack = AsyncExitStack()

    def shutdown(self):
        """Shutdown the MCP connection."""
        self._shutdown_event.set()

    async def wait_for_shutdown(self):
        """Wait for the MCP connection to be shutdown."""
        await self._shutdown_event.wait()
        self.status = McpServerStatus.DISCONNECTED

    async def wait_for_initialize(self):
        """Wait for the MCP connection to be initialized."""
        await self._initialize_event.wait()
        self.status = McpServerStatus.CONNECTED

    async def connect(self):
        """Connect to the MCP server."""
        if self.config.type == "stdio":
            await self._connect_to_stdio_server()
        elif self.config.type == "sse":
            await self._connect_to_sse_server()
        elif self.config.type == "websocket":
            raise NotImplementedError("Websocket not supported yet.")
        else:
            raise ValueError("Unknown MCP server type.")
        await self._initialize()

    async def _connect_to_stdio_server(self):
        """Connect to a stdio server."""
        server_params = StdioServerParameters(
            command=self.config.command, args=self.config.args, env=self.config.env
        )
        # 自动启动 stdio mcp server
        transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params),
        )
        read_stream, write_stream = transport
        # 创建并打开 session
        self._session = await self._exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
        # NOTE: 此时还未初始化完成
        
    async def _connect_to_sse_server(self):
        """Connect to a SSE server."""
        transport = await self._exit_stack.enter_async_context(
            sse_client(self.config.url),
        )
        read_stream, write_stream = transport
        # 创建并打开 session
        self._session = await self._exit_stack.enter_async_context(ClientSession(read_stream, write_stream))

    async def _initialize(self):
        """Initialize the MCP connection."""
        initialize_result = await self._session.initialize()
        self.server_info = {
            "name": initialize_result.serverInfo.name,
            "version": initialize_result.serverInfo.version,
        }
        if initialize_result.capabilities.tools:
            list_tools_result = await self._session.list_tools()
            self.tools = [
                self._convert_mcp_tool_schema(mcp_tool)
                for mcp_tool in list_tools_result.tools
            ]
        if initialize_result.capabilities.prompts:
            self.prompts = await self._session.list_prompts()
        if initialize_result.capabilities.resources:
            self.resources = await self._session.list_resources()
        self._initialize_event.set()

    def _convert_mcp_tool_schema(self, mcp_tool: mcp_types.Tool) -> ToolSchema:
        """Convert a MCP tool schema to a ToolSchema."""
        # 过滤掉 inputSchema 中名为
        tool_schema = ToolSchema(
            type="function",
            function={
                "name": mcp_tool.name,
                "description": mcp_tool.description,
                "parameters": mcp_tool.inputSchema.get("properties", {}),
            },
        )
        return tool_schema

    def get_tool(self, tool_name: str) -> Optional[ToolSchema]:
        """Get a tool."""
        for tool in self.tools:
            if tool["function"]["name"] == tool_name:
                return tool
        return None

    async def call_tool(self, name: str, arguments: dict) -> mcp_types.CallToolResult:
        """Call a tool."""
        return await self._session.call_tool(name, arguments)
    
    def call_tool_sync(self, name: str, arguments: dict) -> mcp_types.CallToolResult:
        """Call a tool synchronously."""
        future = asyncio.run_coroutine_threadsafe(self.call_tool(name, arguments), McpHub.get_instance()._background_loop)
        return future.result()

    async def read_resource(self, uri: str) -> mcp_types.ReadResourceResult:
        """Read a resource."""
        return await self._session.read_resource(uri)


async def mcp_connection_lifecycle_task(mcp_connection: McpConnection):
    """MCP connection lifecycle task."""
    name = mcp_connection.name
    logger.info(f"starting MCP connection lifecycle task for {name}")
    try:
        await mcp_connection.connect()
        await mcp_connection.wait_for_shutdown()
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error in MCP connection lifecycle task for {name}: {e}")
        logger.debug(error_details)
        mcp_connection.error = str(e)
        mcp_connection.status = McpServerStatus.DISCONNECTED


class McpHub:
    """MCP Manager."""

    connections: List[McpConnection] = []
    _instance: "McpHub" = None

    def __init__(self) -> None:
        """Initialize the MCP manager."""
        self._lock = None
        self._task_group: Optional[TaskGroup] = None
        
        # 以下为后台服务相关属性
        self._server_thread: Optional[threading.Thread] = None
        self._background_loop: Optional[asyncio.AbstractEventLoop] = None
        self._server_initialize_event = threading.Event()
        self._server_shutdown_event = threading.Event()

    def __new__(cls) -> Self:
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> Self:
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = cls()
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
                if "command" in server_config:
                    server_config["type"] = "stdio"
                elif "url" in server_config:
                    server_url = server_config["url"]
                    if server_url.startswith("http"):
                        server_config["type"] = "sse"
                    elif server_url.startswith("ws"):
                        server_config["type"] = "websocket"
                    else:
                        raise ValueError("Unknown MCP server type.")
                else:
                    raise ValueError("Unknown MCP server type.")
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

    async def _initialize_mcp_servers(self):
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
            await self._update_mcp_connections(mcp_server_setting)
        except Exception as e:
            logger.error(f"Error updating MCP connections: {e}")
            return
        logger.info("mcp servers initialized.")

    async def _get_mcp_connection(self, server_name: str) -> Optional[McpConnection]:
        """Get a MCP connection."""
        connection = None
        async with self._lock:
            for conn in self.connections:
                if conn.name == server_name:
                    connection = conn
                    break
        return connection
    
    def get_mcp_connection(self, server_name: str) -> Optional[McpConnection]:
        """Get a MCP connection."""
        future = asyncio.run_coroutine_threadsafe(self._get_mcp_connection(server_name), self._background_loop)
        return future.result()

    async def _add_mcp_connection(
        self,
        name: str,
        config: Union[StdioServerConfig, SSEServerConfig, WebsocketServerConfig],
    ):
        """Add a MCP connection.

        Args:
            name (str): Server name.
            config (Union[StdioServerConfig, SSEServerConfig, WebsocketServerConfig]): Server configuration.
        """
        if self._task_group is None:
            self._task_group = create_task_group()
            await self._task_group.__aenter__()
        mcp_connection = McpConnection(name=name, config=config)
        # 启动连接
        self._task_group.start_soon(
            mcp_connection_lifecycle_task,
            mcp_connection,
            name=f"mcp_connection_lifecycle_task-{name}",
        )
        await mcp_connection.wait_for_initialize()
        self.connections.append(mcp_connection)

    async def _update_mcp_connections(self, mcp_server_setting: MCPServerSetting):
        """Update all MCP connections."""
        async with self._lock:
            currnet_server_names = [connection.name for connection in self.connections]
            new_server_names = [
                server_name for server_name in mcp_server_setting.mcpServers.keys()
            ]
            # 删除连接
            for server_name in currnet_server_names:
                if server_name not in new_server_names:
                    await self._remove_mcp_connection(server_name)
                    logger.info(f"Removed MCP connection [{server_name}]")
            # 添加或更新连接
            for server_name, server_config in mcp_server_setting.mcpServers.items():
                if server_name in currnet_server_names:
                    try:
                        await self._remove_mcp_connection(server_name)
                        await self._add_mcp_connection(server_name, server_config)
                        logger.info(f"update MCP connection [{server_name}]")
                    except Exception as e:
                        logger.error(
                            f"Error updating MCP connection [{server_name}]: {e}"
                        )
                        continue
                else:
                    try:
                        await self._add_mcp_connection(server_name, server_config)
                        logger.info(f"add MCP connection [{server_name}]")
                    except Exception as e:
                        error_details = traceback.format_exc()
                        print(error_details)
                        logger.error(
                            f"Error adding MCP connection [{server_name}]: {e}"
                        )
                        continue

    async def _remove_mcp_connection(self, server_name: str):
        """Remove a MCP connection."""
        connection = await self._get_mcp_connection(server_name)
        if connection:
            connection.shutdown()
            self.connections.remove(connection)

    async def _remove_all_connections(self):
        """Close all MCP connections."""
        async with self._lock:
            for connection in self.connections:
                connection.shutdown()
                logger.info(f"shutting down MCP connection [{connection.name}]")
            self.connections = []

    @property
    def is_initialized(self) -> bool:
        """Check if MCP servers are initialized.

        Returns:
            bool: True if MCP servers are initialized, False otherwise.
        """
        return self._server_initialize_event.is_set()

    def list_connections(self) -> List[str]:
        """List all MCP connections."""
        return [connection.name for connection in self.connections]

    def list_tools(self) -> Dict[str, List[ToolSchema]]:
        """List all tools."""
        tools = {}
        for connection in self.connections:
            tools[connection.name] = connection.tools
        return tools

    async def _async_launch_mcp_servers(self):
        """Asynchronously launch MCP servers.
        First initialize the service and wait for the shutdown signal, then close all connections.
        """
        # ✅ 在事件循环中初始化 asyncio.Lock
        self._lock = asyncio.Lock()
        logger.info("launching MCP servers...")
        await self._initialize_mcp_servers()
        self._server_initialize_event.set()
        logger.info("mcp servers launched.")
        # 异步等待关闭信号（将阻塞操作转为异步调用）
        # await anyio.from_thread.run_sync(self._server_shutdown_event.wait)
        self._server_shutdown_event.wait()
        logger.info("shutting down MCP servers...")
        await self._remove_all_connections()
        logger.info("MCP servers shutdown.")
        
    def launch_mcp_servers(self):
        """Launch MCP servers in a background thread.
        This method will block until the initialization is complete.
        """
        if self._server_thread is not None and self._server_thread.is_alive() and self._server_initialize_event.is_set():
            return
        self._server_initialize_event.clear()
        self._server_shutdown_event.clear()
        self._background_loop = asyncio.new_event_loop()

        # def run_loop():
        #     asyncio.set_event_loop(self._background_loop)
        #     # 将异步启动任务调度到后台事件循环中
        #     self._background_loop.create_task(self._async_launch_mcp_servers())
        #     self._background_loop.run_forever()
        def run_loop():
            asyncio.set_event_loop(self._background_loop)

            # ✅ 保证 _async_launch_mcp_servers 执行完才 set_event
            async def runner():
                await self._async_launch_mcp_servers()
                self._server_initialize_event.set()

            self._background_loop.run_until_complete(runner())
            self._background_loop.run_forever()

        self._server_thread = threading.Thread(
            target=run_loop,
            daemon=True,
        )
        self._server_thread.start()
        # 阻塞等待 MCP 服务器初始化完成
        self._server_initialize_event.wait()
        
    def shutdown_mcp_servers(self):
        """Shutdown the MCP servers service, send the shutdown signal and wait for the background thread to exit.
        """
        self._server_shutdown_event.set()
        if self._background_loop is not None:
            self._background_loop.call_soon_threadsafe(self._background_loop.stop)
        if self._server_thread is not None:
            self._server_thread.join()
        self._server_shutdown_event.clear()
        self._server_initialize_event.clear()
        self._background_loop = None
        self._server_thread = None
    
if __name__ == "__main__":
    hub = McpHub.get_instance()
    try:
        hub.launch_mcp_servers()
        while True:
            user_input = input("Enter command: ").strip()
            if user_input == "list":
                for connection in hub.connections:
                    print(f"{connection.name}: {connection.status}")
            elif user_input == "tools":
                for connection in hub.connections:
                    print(f"{connection.name}: {connection.tools}")
            elif user_input == "prompts":
                for connection in hub.connections:
                    print(f"{connection.name}: {connection.prompts}")
            elif user_input == "resources":
                for connection in hub.connections:
                    print(f"{connection.name}: {connection.resources}")
            elif user_input == "restart":
                hub.shutdown_mcp_servers()
                hub.launch_mcp_servers()
            elif user_input == "exit":
                break
    finally:
        hub.shutdown_mcp_servers()
