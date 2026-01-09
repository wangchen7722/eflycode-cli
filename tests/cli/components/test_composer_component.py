"""ComposerComponent 异步测试"""

import asyncio
import unittest

from eflycode.cli.components.composer import ComposerComponent
from tests.utils.async_test_case import AsyncTestCase


class TestComposerComponent(AsyncTestCase):
    """ComposerComponent 异步测试类"""

    def test_show_basic(self):
        """测试基本的 show 方法"""
        async def _test():
            component = ComposerComponent()
            # 由于需要用户交互，这里只测试组件创建
            self.assertIsNotNone(component)
        
        asyncio.run(_test())

    def test_show_is_async(self):
        """测试 show 方法是异步的"""
        async def _test():
            component = ComposerComponent()
            # 验证 show 方法是异步的
            self.assertTrue(hasattr(component, 'show'))
            self.assertTrue(asyncio.iscoroutinefunction(component.show))
        
        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()

