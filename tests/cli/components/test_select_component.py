"""SelectComponent 异步测试"""

import asyncio
import unittest
from unittest.mock import patch

from eflycode.cli.components.select import SelectComponent
from eflycode.core.ui.errors import UserCanceledError
from tests.utils.async_test_case import AsyncTestCase


class TestSelectComponent(AsyncTestCase):
    """SelectComponent 异步测试类"""

    def test_show_basic(self):
        """测试基本的 show 方法"""
        async def _test():
            component = SelectComponent()
            # 由于需要用户交互，这里只测试组件创建
            # 实际的选择测试需要模拟或集成测试
            self.assertIsNotNone(component)
        
        asyncio.run(_test())

    def test_show_with_options(self):
        """测试带选项的 show 方法"""
        async def _test():
            component = SelectComponent()
            # 注意：实际的 show 调用需要终端交互
            # 这里只验证方法存在且可调用
            self.assertTrue(hasattr(component, 'show'))
            self.assertTrue(asyncio.iscoroutinefunction(component.show))
        
        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()

