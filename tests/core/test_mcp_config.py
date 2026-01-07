"""MCP配置加载测试"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from eflycode.core.mcp.config import (
    MCPServerConfig,
    find_mcp_config_file,
    load_mcp_config,
)
from eflycode.core.mcp.errors import MCPConfigError


class TestMCPServerConfig(unittest.TestCase):
    """MCP服务器配置测试类"""

    def test_expand_env_vars(self):
        """测试环境变量展开"""
        # 先设置环境变量
        os.environ["TEST_API_KEY"] = "test-key-123"

        try:
            config = MCPServerConfig(
                name="test",
                transport="stdio",
                command="npx",
                args=["-y", "test-server"],
                env={"API_KEY": "${TEST_API_KEY}"},
            )

            # 验证环境变量已展开
            self.assertEqual(config.env["API_KEY"], "test-key-123")
        finally:
            # 清理
            del os.environ["TEST_API_KEY"]

    def test_no_env(self):
        """测试无环境变量的配置"""
        config = MCPServerConfig(
            name="test",
            transport="stdio",
            command="npx",
            args=["-y", "test-server"],
        )

        self.assertEqual(config.env, {})
        self.assertEqual(config.name, "test")
        self.assertEqual(config.transport, "stdio")
        self.assertEqual(config.command, "npx")
        self.assertEqual(config.args, ["-y", "test-server"])

    def test_http_config(self):
        """测试HTTP传输配置"""
        config = MCPServerConfig(
            name="http-server",
            transport="http",
            url="https://example.com/mcp",
        )

        self.assertEqual(config.name, "http-server")
        self.assertEqual(config.transport, "http")
        self.assertEqual(config.url, "https://example.com/mcp")
        self.assertIsNone(config.command)
        self.assertEqual(config.args, [])

    def test_to_http_params(self):
        """测试HTTP参数转换"""
        config = MCPServerConfig(
            name="http-server",
            transport="http",
            url="https://example.com/mcp",
        )

        url = config.to_http_params()
        self.assertEqual(url, "https://example.com/mcp")

    def test_to_http_params_missing_url(self):
        """测试HTTP参数转换缺少URL"""
        config = MCPServerConfig(
            name="http-server",
            transport="http",
            url=None,
        )

        with self.assertRaises(ValueError):
            config.to_http_params()


class TestMCPConfigLoading(unittest.TestCase):
    """MCP配置加载测试类"""

    def setUp(self):
        """设置测试环境"""
        self.tmp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """清理测试环境"""
        import shutil

        shutil.rmtree(self.tmp_dir)

    def test_find_mcp_config_file_not_found(self):
        """测试查找不存在的配置文件"""
        result = find_mcp_config_file(self.tmp_dir)
        self.assertIsNone(result)

    def test_find_mcp_config_file_in_workspace(self):
        """测试在工作区目录查找配置文件"""
        workspace_dir = self.tmp_dir / "workspace"
        workspace_dir.mkdir()
        config_dir = workspace_dir / ".eflycode"
        config_dir.mkdir()
        config_file = config_dir / "mcp.json"
        config_file.write_text('{"mcpServers": {}}')

        result = find_mcp_config_file(workspace_dir)
        self.assertEqual(result, config_file)

    def test_load_mcp_config_valid(self):
        """测试加载有效的MCP配置"""
        config_dir = self.tmp_dir / ".eflycode"
        config_dir.mkdir()
        config_file = config_dir / "mcp.json"

        config_data = {
            "mcpServers": {
                "test_server": {
                    "command": "npx",
                    "args": ["-y", "test-server"],
                }
            }
        }

        config_file.write_text(json.dumps(config_data, indent=2))

        configs = load_mcp_config(self.tmp_dir)
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0].name, "test_server")
        self.assertEqual(configs[0].transport, "stdio")
        self.assertEqual(configs[0].command, "npx")
        self.assertEqual(configs[0].args, ["-y", "test-server"])

    def test_load_mcp_config_with_env(self):
        """测试加载包含环境变量的MCP配置"""
        os.environ["TEST_TOKEN"] = "test-token-value"

        config_dir = self.tmp_dir / ".eflycode"
        config_dir.mkdir()
        config_file = config_dir / "mcp.json"

        config_data = {
            "mcpServers": {
                "test_server": {
                    "command": "npx",
                    "args": ["-y", "test-server"],
                    "env": {
                        "API_TOKEN": "${TEST_TOKEN}",
                    },
                }
            }
        }

        config_file.write_text(json.dumps(config_data, indent=2))

        configs = load_mcp_config(self.tmp_dir)
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0].env["API_TOKEN"], "test-token-value")

        # 清理
        del os.environ["TEST_TOKEN"]

    def test_load_mcp_config_invalid_json(self):
        """测试加载无效的JSON配置"""
        config_dir = self.tmp_dir / ".eflycode"
        config_dir.mkdir()
        config_file = config_dir / "mcp.json"
        config_file.write_text("{ invalid json }")

        with self.assertRaises(MCPConfigError):
            load_mcp_config(self.tmp_dir)

    def test_load_mcp_config_missing_command(self):
        """测试缺少command字段的配置"""
        config_dir = self.tmp_dir / ".eflycode"
        config_dir.mkdir()
        config_file = config_dir / "mcp.json"

        config_data = {
            "mcpServers": {
                "test_server": {
                    "args": ["-y", "test-server"],
                }
            }
        }

        config_file.write_text(json.dumps(config_data, indent=2))

        configs = load_mcp_config(self.tmp_dir)
        # 应该跳过无效配置
        self.assertEqual(len(configs), 0)

    def test_load_mcp_config_http(self):
        """测试加载HTTP传输配置"""
        config_dir = self.tmp_dir / ".eflycode"
        config_dir.mkdir()
        config_file = config_dir / "mcp.json"

        config_data = {
            "mcpServers": {
                "http_server": {
                    "transport": "http",
                    "url": "https://example.com/mcp",
                }
            }
        }

        config_file.write_text(json.dumps(config_data, indent=2))

        configs = load_mcp_config(self.tmp_dir)
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0].name, "http_server")
        self.assertEqual(configs[0].transport, "http")
        self.assertEqual(configs[0].url, "https://example.com/mcp")

    def test_load_mcp_config_http_missing_url(self):
        """测试HTTP传输缺少URL字段"""
        config_dir = self.tmp_dir / ".eflycode"
        config_dir.mkdir()
        config_file = config_dir / "mcp.json"

        config_data = {
            "mcpServers": {
                "http_server": {
                    "transport": "http",
                }
            }
        }

        config_file.write_text(json.dumps(config_data, indent=2))

        configs = load_mcp_config(self.tmp_dir)
        # 应该跳过无效配置
        self.assertEqual(len(configs), 0)

    def test_load_mcp_config_mixed_transports(self):
        """测试混合传输类型配置"""
        config_dir = self.tmp_dir / ".eflycode"
        config_dir.mkdir()
        config_file = config_dir / "mcp.json"

        config_data = {
            "mcpServers": {
                "stdio_server": {
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["-y", "test-server"],
                },
                "http_server": {
                    "transport": "http",
                    "url": "https://example.com/mcp",
                }
            }
        }

        config_file.write_text(json.dumps(config_data, indent=2))

        configs = load_mcp_config(self.tmp_dir)
        self.assertEqual(len(configs), 2)
        
        stdio_config = next(c for c in configs if c.name == "stdio_server")
        http_config = next(c for c in configs if c.name == "http_server")
        
        self.assertEqual(stdio_config.transport, "stdio")
        self.assertEqual(stdio_config.command, "npx")
        
        self.assertEqual(http_config.transport, "http")
        self.assertEqual(http_config.url, "https://example.com/mcp")

    def test_load_mcp_config_default_transport(self):
        """测试默认传输类型为stdio"""
        config_dir = self.tmp_dir / ".eflycode"
        config_dir.mkdir()
        config_file = config_dir / "mcp.json"

        config_data = {
            "mcpServers": {
                "test_server": {
                    "command": "npx",
                    "args": ["-y", "test-server"],
                }
            }
        }

        config_file.write_text(json.dumps(config_data, indent=2))

        configs = load_mcp_config(self.tmp_dir)
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0].transport, "stdio")

    def test_load_mcp_config_not_found(self):
        """测试配置文件不存在的情况"""
        configs = load_mcp_config(Path("/nonexistent/path"))
        self.assertEqual(len(configs), 0)


if __name__ == "__main__":
    unittest.main()
