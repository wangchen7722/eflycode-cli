"""MCP配置管理模块

负责从.eflycode/mcp.json加载MCP服务器配置
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from eflycode.core.config.config_manager import (
    get_user_config_dir,
    resolve_workspace_dir,
)
from eflycode.core.mcp.errors import MCPConfigError
from eflycode.core.utils.logger import logger


class MCPServerConfig:
    """MCP服务器配置"""

    def __init__(
        self,
        name: str,
        transport: str = "stdio",
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        url: Optional[str] = None,
    ):
        """初始化MCP服务器配置

        Args:
            name: 服务器名称，用于命名空间前缀
            transport: 传输类型，stdio 或 http，默认为 stdio
            command: 启动命令，stdio 传输时必需
            args: 命令参数列表，stdio 传输时使用
            env: 环境变量字典，支持使用${VAR_NAME}格式引用环境变量，stdio 传输时使用
            url: 服务器 URL，http 传输时必需
        """
        self.name = name
        self.transport = transport
        self.command = command
        self.args = args or []
        self.env = self._expand_env_vars(env or {})
        self.url = url

    def _expand_env_vars(self, env: Dict[str, str]) -> Dict[str, str]:
        """展开环境变量引用

        支持使用${VAR_NAME}格式引用环境变量

        Args:
            env: 环境变量字典

        Returns:
            展开后的环境变量字典
        """
        expanded = {}
        for key, value in env.items():
            # 支持${VAR_NAME}格式
            pattern = r"\$\{([^}]+)\}"
            match = re.search(pattern, value)
            if match:
                var_name = match.group(1)
                env_value = os.getenv(var_name, "")
                expanded[key] = value.replace(match.group(0), env_value)
            else:
                expanded[key] = value
        return expanded

    def to_stdio_params(self):
        """转换为StdioServerParameters对象

        Returns:
            StdioServerParameters: MCP SDK的服务器参数对象
        """
        from mcp.client.stdio import StdioServerParameters

        return StdioServerParameters(
            command=self.command,
            args=self.args,
            env=self.env if self.env else None,
        )

    def to_http_params(self) -> str:
        """返回HTTP传输所需的URL

        Returns:
            str: MCP服务器URL
        """
        if not self.url:
            raise ValueError("HTTP传输需要提供url字段")
        return self.url


def find_mcp_config_file() -> Optional[Path]:
    """查找MCP配置文件

    查找逻辑：
    1. 从工作区目录的.eflycode/mcp.json查找
    2. 如果未找到，从用户主目录的.eflycode/mcp.json查找

    Returns:
        Optional[Path]: 配置文件路径，如果未找到则返回None
    """
    # 先查找工作区目录
    workspace_dir = resolve_workspace_dir()
    workspace_config = workspace_dir / ".eflycode" / "mcp.json"
    if workspace_config.exists() and workspace_config.is_file():
        return workspace_config

    # 再查找用户主目录
    user_config = get_user_config_dir() / "mcp.json"
    if user_config.exists() and user_config.is_file():
        return user_config

    return None


def load_mcp_config() -> List[MCPServerConfig]:
    """加载MCP配置

    从.eflycode/mcp.json加载MCP服务器配置

    Returns:
        List[MCPServerConfig]: MCP服务器配置列表

    Raises:
        MCPConfigError: 当配置加载或解析失败时抛出
    """
    config_path = find_mcp_config_file()

    if config_path is None:
        logger.debug("未找到MCP配置文件，跳过MCP服务器加载")
        return []

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
    except json.JSONDecodeError as e:
        raise MCPConfigError(
            message=f"MCP配置文件JSON解析失败: {config_path}",
            details=str(e),
        ) from e
    except Exception as e:
        raise MCPConfigError(
            message=f"读取MCP配置文件失败: {config_path}",
            details=str(e),
        ) from e

    # 解析mcpServers配置
    mcp_servers = config_data.get("mcpServers", {})
    if not isinstance(mcp_servers, dict):
        raise MCPConfigError(
            message="MCP配置格式错误: mcpServers必须是对象",
            details=f"当前类型: {type(mcp_servers)}",
        )

    server_configs = []
    for server_name, server_config in mcp_servers.items():
        if not isinstance(server_config, dict):
            logger.warning(f"MCP服务器配置格式错误: {server_name}，跳过")
            continue

        transport = server_config.get("transport", "stdio")
        if transport not in ("stdio", "http"):
            logger.warning(f"MCP服务器配置transport字段无效: {server_name}，必须是stdio或http，跳过")
            continue

        if transport == "http":
            url = server_config.get("url")
            if not url:
                logger.warning(f"MCP服务器配置缺少url字段: {server_name}，HTTP传输需要url，跳过")
                continue
            try:
                server_config_obj = MCPServerConfig(
                    name=server_name,
                    transport="http",
                    url=url,
                )
                server_configs.append(server_config_obj)
                logger.info(f"加载MCP服务器配置: {server_name}，传输类型: http")
            except Exception as e:
                logger.warning(f"加载MCP服务器配置失败: {server_name}，错误: {e}，跳过")
                continue
        else:  # stdio
            command = server_config.get("command")
            if not command:
                logger.warning(f"MCP服务器配置缺少command字段: {server_name}，stdio传输需要command，跳过")
                continue

            args = server_config.get("args", [])
            if not isinstance(args, list):
                logger.warning(f"MCP服务器配置args字段必须是数组: {server_name}，跳过")
                continue

            env = server_config.get("env")
            if env is not None and not isinstance(env, dict):
                logger.warning(f"MCP服务器配置env字段必须是对象: {server_name}，跳过")
                continue

            try:
                server_config_obj = MCPServerConfig(
                    name=server_name,
                    transport="stdio",
                    command=command,
                    args=args,
                    env=env,
                )
                server_configs.append(server_config_obj)
                logger.info(f"加载MCP服务器配置: {server_name}，传输类型: stdio")
            except Exception as e:
                logger.warning(f"加载MCP服务器配置失败: {server_name}，错误: {e}，跳过")
                continue

    return server_configs

