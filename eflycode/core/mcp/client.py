"""MCP客户端封装

使用官方MCP Python SDK封装MCP客户端，提供同步接口适配
使用多线程和队列方式处理异步操作
"""

import asyncio
import json
import queue
import sys
import threading
import time
from typing import Any, Dict, List, Optional

from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client

from eflycode.core.mcp.config import MCPServerConfig
from eflycode.core.mcp.errors import (
    MCPConnectionError,
    MCPProtocolError,
    MCPToolError,
)
from eflycode.core.utils.logger import logger


class MCPClient:
    """MCP客户端

    封装官方MCP SDK的ClientSession，使用线程和队列提供同步接口
    """

    def __init__(self, server_config: MCPServerConfig):
        """初始化MCP客户端

        Args:
            server_config: MCP服务器配置
        """
        self.server_config = server_config
        self.server_name = server_config.name
        self._session: Optional[ClientSession] = None
        self._read = None
        self._write = None
        self._transport = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._tools_cache: Optional[List[Dict[str, Any]]] = None
        self._connected = False
        self._connecting = False
        self._lock = threading.Lock()
        self._request_queue: queue.Queue = queue.Queue()
        self._response_queue: queue.Queue = queue.Queue()
        self._shutdown_event = threading.Event()

    def start_connect(self) -> None:
        """异步启动连接MCP服务器

        在后台线程中启动连接，不阻塞主线程
        连接状态可以通过is_connected方法检查
        """
        with self._lock:
            if self._connected or self._connecting:
                return
            self._connecting = True

        try:
            # 创建新的事件循环
            # Windows上使用ProactorEventLoop以支持子进程，Linux和Mac使用默认事件循环
            if sys.platform == "win32":
                self._loop = asyncio.ProactorEventLoop()
            else:
                self._loop = asyncio.new_event_loop()

            # 在独立线程中运行事件循环
            self._thread = threading.Thread(
                target=self._run_event_loop,
                daemon=True,
                name=f"MCPClient-{self.server_name}",
            )
            self._thread.start()

            # 通过队列发送连接请求，不等待结果
            request_id = "connect"
            self._request_queue.put(("connect", request_id, None))
            logger.info(f"已启动MCP服务器连接: {self.server_name}，连接在后台进行")
        except Exception as e:
            with self._lock:
                self._connected = False
                self._connecting = False
            logger.error(f"启动MCP服务器连接失败: {self.server_name}，错误: {e}")

    def connect(self, timeout: Optional[float] = None) -> None:
        """连接到MCP服务器

        同步等待连接完成，如果连接未启动则先启动连接

        Args:
            timeout: 超时时间，单位为秒，None表示使用默认10秒

        Raises:
            MCPConnectionError: 当连接失败时抛出
        """
        with self._lock:
            if self._connected:
                return

        # 如果未启动连接，先启动
        if not self._connecting and self._loop is None:
            self.start_connect()

        # 等待事件循环启动，最多等待5秒
        for _ in range(50):
            if self._loop and self._loop.is_running():
                break
            time.sleep(0.1)
        else:
            raise MCPConnectionError(
                message=f"启动事件循环失败: {self.server_name}",
                details="事件循环未能启动",
            )

        # 等待连接结果
        wait_timeout = timeout if timeout is not None else 10
        start_time = time.time()
        
        # 从响应队列中查找连接响应
        pending_responses = []
        found_connect_response = False
        connect_success = False
        connect_result = None
        
        try:
            while time.time() - start_time < wait_timeout:
                try:
                    response_id, success, result = self._response_queue.get(timeout=0.5)
                    if response_id == "connect":
                        found_connect_response = True
                        connect_success = success
                        connect_result = result
                        break
                    else:
                        # 保存非连接响应，稍后放回队列
                        pending_responses.append((response_id, success, result))
                except queue.Empty:
                    # 检查是否已连接
                    with self._lock:
                        if self._connected:
                            found_connect_response = True
                            connect_success = True
                            break
                    continue
            
            # 将非连接响应放回队列
            for response in pending_responses:
                self._response_queue.put(response)
            
            if not found_connect_response:
                with self._lock:
                    self._connecting = False
                raise MCPConnectionError(
                    message=f"连接MCP服务器超时: {self.server_name}",
                    details=f"连接建立超过{wait_timeout}秒",
                )
            
            if not connect_success:
                # 提取更详细的错误信息
                error_details = "未知错误"
                if isinstance(connect_result, Exception):
                    error_details = f"{type(connect_result).__name__}: {str(connect_result)}"
                    # 如果是子进程错误，尝试提取更详细的信息
                    if hasattr(connect_result, "stderr") and connect_result.stderr:
                        error_details += f"，stderr: {connect_result.stderr.decode('utf-8', errors='ignore')[:200]}"
                elif connect_result:
                    error_details = str(connect_result)
                
                with self._lock:
                    self._connecting = False
                raise MCPConnectionError(
                    message=f"连接MCP服务器失败: {self.server_name}",
                    details=error_details,
                )

            with self._lock:
                if not self._connected:
                    self._connecting = False
                    raise MCPConnectionError(
                        message=f"连接MCP服务器失败: {self.server_name}",
                        details="连接未成功建立",
                    )
                self._connecting = False

            logger.info(f"MCP服务器连接成功: {self.server_name}")
        except MCPConnectionError:
            raise
        except Exception as e:
            with self._lock:
                self._connecting = False
            raise MCPConnectionError(
                message=f"连接MCP服务器失败: {self.server_name}",
                details=str(e),
            ) from e

    def is_connected(self) -> bool:
        """检查是否已连接

        Returns:
            bool: 已连接返回True，未连接返回False
        """
        with self._lock:
            return self._connected

    def wait_for_connection(self, timeout: Optional[float] = None) -> bool:
        """等待连接完成

        Args:
            timeout: 超时时间，单位为秒，如果为None则使用默认10秒

        Returns:
            bool: 连接成功返回True，超时返回False
        """
        try:
            self.connect(timeout=timeout)
            return True
        except MCPConnectionError:
            return False

    def _run_event_loop(self) -> None:
        """运行事件循环，在线程中执行

        处理来自队列的请求，执行异步操作，将结果放回响应队列
        """
        asyncio.set_event_loop(self._loop)

        async def process_requests():
            """处理请求循环"""
            while not self._shutdown_event.is_set():
                try:
                    # 从队列获取请求，超时时间0.1秒
                    try:
                        request_type, request_id, request_data = self._request_queue.get(
                            timeout=0.1
                        )
                    except queue.Empty:
                        await asyncio.sleep(0.01)
                        continue

                    try:
                        if request_type == "connect":
                            await self._connect_async()
                            self._response_queue.put((request_id, True, None))
                        elif request_type == "disconnect":
                            await self._disconnect_async()
                            self._response_queue.put((request_id, True, None))
                        elif request_type == "list_tools":
                            result = await self._list_tools_async()
                            self._response_queue.put((request_id, True, result))
                        elif request_type == "call_tool":
                            tool_name, arguments = request_data
                            result = await self._call_tool_async(tool_name, arguments)
                            self._response_queue.put((request_id, True, result))
                        else:
                            self._response_queue.put(
                                (request_id, False, f"未知请求类型: {request_type}")
                            )
                    except Exception as e:
                        self._response_queue.put((request_id, False, e))

                except Exception as e:
                    logger.error(f"MCP事件循环处理请求时出错: {self.server_name}，错误: {e}")

        # 运行事件循环
        try:
            self._loop.run_until_complete(process_requests())
        except Exception as e:
            logger.error(f"MCP事件循环运行失败: {self.server_name}，错误: {e}")
        finally:
            self._loop.close()

    async def _connect_async(self) -> None:
        """异步连接MCP服务器

        在事件循环线程中执行
        """
        try:
            if self.server_config.transport == "http":
                from mcp.client.streamable_http import streamable_http_client
                
                url = self.server_config.to_http_params()
                self._transport = streamable_http_client(url)
                self._read, self._write, _ = await self._transport.__aenter__()
            else:  # stdio
                server_params = self.server_config.to_stdio_params()
                self._transport = stdio_client(server_params)
                self._read, self._write = await self._transport.__aenter__()

            self._session = ClientSession(self._read, self._write)
            await self._session.__aenter__()
            await self._session.initialize()

            with self._lock:
                self._connected = True
                self._connecting = False
            logger.debug(f"MCP服务器异步连接成功: {self.server_name}，传输类型: {self.server_config.transport}")
        except Exception as e:
            with self._lock:
                self._connected = False
                self._connecting = False
            logger.error(f"MCP服务器异步连接失败: {self.server_name}，传输类型: {self.server_config.transport}，错误: {e}")
            raise

    def disconnect(self) -> None:
        """断开MCP服务器连接"""
        with self._lock:
            if not self._connected:
                return
            self._connected = False

        try:
            # 通过队列发送断开请求
            request_id = "disconnect"
            self._request_queue.put(("disconnect", request_id, None))

            # 等待断开结果，最多等待5秒
            try:
                response_id, success, result = self._response_queue.get(timeout=5)
                if response_id != request_id:
                    logger.warning(
                        f"断开MCP服务器连接时响应ID不匹配: {self.server_name}"
                    )
            except queue.Empty:
                logger.warning(f"断开MCP服务器连接超时: {self.server_name}")

            # 停止事件循环
            self._shutdown_event.set()

            # 等待线程结束
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2)

            logger.info(f"MCP服务器已断开: {self.server_name}")
        except Exception as e:
            logger.warning(f"断开MCP服务器连接失败: {self.server_name}，错误: {e}")

    async def _disconnect_async(self) -> None:
        """异步断开MCP服务器连接

        在事件循环线程中执行
        """
        try:
            if self._session:
                await self._session.__aexit__(None, None, None)
            if self._transport:
                await self._transport.__aexit__(None, None, None)
        except Exception as e:
            logger.warning(f"异步断开MCP服务器连接时出错: {self.server_name}，错误: {e}")

    def list_tools(self) -> List[Dict[str, Any]]:
        """列出可用工具

        Returns:
            List[Dict[str, Any]]: 工具列表，每个工具包含name、description、inputSchema字段

        Raises:
            MCPConnectionError: 当未连接时抛出
            MCPProtocolError: 当协议通信失败时抛出
        """
        with self._lock:
            if not self._connected:
                raise MCPConnectionError(
                    message=f"MCP服务器未连接: {self.server_name}",
                    details="请先调用connect方法",
                )

        # 如果缓存存在，直接返回
        if self._tools_cache is not None:
            return self._tools_cache

        try:
            # 通过队列发送请求
            request_id = f"list_tools_{time.time()}"
            self._request_queue.put(("list_tools", request_id, None))

            # 等待响应，最多等待10秒
            try:
                response_id, success, result = self._response_queue.get(timeout=10)
                if response_id != request_id:
                    raise MCPProtocolError(
                        message=f"获取MCP服务器工具列表失败: {self.server_name}",
                        details="响应ID不匹配",
                    )
                if not success:
                    raise MCPProtocolError(
                        message=f"获取MCP服务器工具列表失败: {self.server_name}",
                        details=str(result) if result else "未知错误",
                    )

                tools_result = result

                # 转换为字典列表
                tools = []
                for tool in tools_result.tools:
                    tools.append({
                        "name": tool.name,
                        "description": tool.description or "",
                        "inputSchema": tool.inputSchema if hasattr(tool, "inputSchema") else {},
                    })

                self._tools_cache = tools
                tools_count = len(tools)
                logger.debug(f"MCP服务器工具列表获取成功: {self.server_name}，共{tools_count}个工具")
                return tools
            except queue.Empty:
                raise MCPProtocolError(
                    message=f"获取MCP服务器工具列表超时: {self.server_name}",
                    details="请求超时",
                )
        except Exception as e:
            if isinstance(e, (MCPConnectionError, MCPProtocolError)):
                raise
            raise MCPProtocolError(
                message=f"获取MCP服务器工具列表失败: {self.server_name}",
                details=str(e),
            ) from e

    async def _list_tools_async(self):
        """异步列出工具

        在事件循环线程中执行
        """
        if not self._session:
            raise MCPConnectionError(
                message=f"MCP会话不存在: {self.server_name}",
                details="会话未初始化",
            )
        return await self._session.list_tools()

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """调用工具

        Args:
            tool_name: 工具名称，不包含命名空间前缀
            arguments: 工具参数

        Returns:
            str: 工具执行结果，JSON字符串格式

        Raises:
            MCPConnectionError: 当未连接时抛出
            MCPToolError: 当工具执行失败时抛出
        """
        with self._lock:
            if not self._connected:
                raise MCPConnectionError(
                    message=f"MCP服务器未连接: {self.server_name}",
                    details="请先调用connect方法",
                )

        try:
            # 通过队列发送请求
            request_id = f"call_tool_{time.time()}"
            self._request_queue.put(("call_tool", request_id, (tool_name, arguments)))

            # 等待响应，最多等待120秒，对于需要调用外部API的工具可能需要更长时间
            try:
                response_id, success, result = self._response_queue.get(timeout=120)
                if response_id != request_id:
                    raise MCPToolError(
                        message=f"MCP工具调用失败: {self.server_name}_{tool_name}",
                        tool_name=f"{self.server_name}_{tool_name}",
                        error_details=Exception("响应ID不匹配"),
                    )
                if not success:
                    error = result if isinstance(result, Exception) else Exception(str(result))
                    raise MCPToolError(
                        message=f"MCP工具调用失败: {self.server_name}_{tool_name}",
                        tool_name=f"{self.server_name}_{tool_name}",
                        error_details=error,
                    )

                # 将结果转换为字符串
                # MCP SDK返回的结果包含content字段和structuredContent字段
                result_text = ""
                if hasattr(result, "content") and result.content:
                    # 提取文本内容
                    for content in result.content:
                        if hasattr(content, "text"):
                            result_text += content.text
                        elif hasattr(content, "type") and content.type == "text":
                            result_text += getattr(content, "text", "")

                # 如果有结构化内容，也包含进去
                if hasattr(result, "structuredContent") and result.structuredContent:
                    result_text += "\n" + json.dumps(
                        result.structuredContent, ensure_ascii=False, indent=2
                    )

                if not result_text:
                    result_text = "工具执行成功，但未返回内容"

                logger.debug(f"MCP工具调用成功: {self.server_name}_{tool_name}")
                return result_text
            except queue.Empty:
                raise MCPToolError(
                    message=f"MCP工具调用超时: {self.server_name}_{tool_name}",
                    tool_name=f"{self.server_name}_{tool_name}",
                    error_details=Exception("请求超时，超过120秒未收到响应"),
                )
        except Exception as e:
            if isinstance(e, MCPToolError):
                raise
            # 检查是否是底层 HTTP 客户端的超时错误
            error_str = str(e).lower()
            if "timeout" in error_str or "timed out" in error_str or "read operation" in error_str:
                raise MCPToolError(
                    message=f"MCP工具调用超时: {self.server_name}_{tool_name}",
                    tool_name=f"{self.server_name}_{tool_name}",
                    error_details=Exception(f"底层HTTP客户端读取超时: {e}"),
                ) from e
            raise MCPToolError(
                message=f"MCP工具调用失败: {self.server_name}_{tool_name}",
                tool_name=f"{self.server_name}_{tool_name}",
                error_details=e,
            ) from e

    async def _call_tool_async(self, tool_name: str, arguments: Dict[str, Any]):
        """异步调用工具

        在事件循环线程中执行
        """
        if not self._session:
            raise MCPConnectionError(
                message=f"MCP会话不存在: {self.server_name}",
                details="会话未初始化",
            )
        return await self._session.call_tool(tool_name, arguments=arguments)

    def __enter__(self):
        """上下文管理器入口"""
        self.start_connect()
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()
