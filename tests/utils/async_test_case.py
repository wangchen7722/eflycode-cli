"""异步测试基类

提供使用 unittest + asyncio.run() 进行异步测试的支持
"""

import asyncio
import functools
import unittest


class AsyncTestCase(unittest.TestCase):
    """异步测试基类，使用 asyncio.run() 运行异步测试
    
    使用方法：
    1. 测试类继承 AsyncTestCase
    2. 使用 @AsyncTestCase.async_test 装饰器标记异步测试方法
    3. 或者使用 self.run_async() 在测试方法内部运行异步代码
    """
    
    async def asyncSetUp(self):
        """异步设置方法，子类可以重写"""
        pass
    
    async def asyncTearDown(self):
        """异步清理方法，子类可以重写"""
        pass
    
    def setUp(self):
        """同步设置，调用异步设置"""
        asyncio.run(self.asyncSetUp())
    
    def tearDown(self):
        """同步清理，调用异步清理"""
        asyncio.run(self.asyncTearDown())
    
    def run_async(self, coro):
        """运行异步协程的辅助方法
        
        Args:
            coro: 异步协程对象
            
        Returns:
            协程的返回值
        """
        return asyncio.run(coro)
    
    @staticmethod
    def async_test(coro):
        """装饰器：将异步测试函数包装为同步测试方法
        
        Args:
            coro: 异步测试函数
            
        Returns:
            包装后的同步测试方法
        """
        @functools.wraps(coro)
        def wrapper(self):
            return asyncio.run(coro(self))
        return wrapper

