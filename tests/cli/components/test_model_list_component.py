"""ModelListComponent 异步测试"""

import asyncio
import unittest
from unittest.mock import patch, MagicMock

from eflycode.cli.components.model_list import ModelListComponent
from tests.utils.async_test_case import AsyncTestCase


class TestModelListComponent(AsyncTestCase):
    """ModelListComponent 异步测试类"""

    def test_show_is_async(self):
        """测试 show 方法是异步的"""
        async def _test():
            component = ModelListComponent()
            # 验证 show 方法是异步的
            self.assertTrue(hasattr(component, 'show'))
            self.assertTrue(asyncio.iscoroutinefunction(component.show))
        
        asyncio.run(_test())

    def test_show_with_mock(self):
        """测试 show 方法使用 mock"""
        async def _test():
            # Mock ConfigManager
            mock_config_manager = MagicMock()
            mock_config_manager.get_instance.return_value = mock_config_manager
            mock_config_manager.get_all_model_entries.return_value = [
                {"model": "gpt-4", "name": "GPT-4", "api_key": "sk-test123", "provider": "openai"}
            ]
            mock_config = MagicMock()
            mock_config.model_name = "gpt-4"
            mock_config_manager.get_config.return_value = mock_config
            mock_config_manager.get_model_entry_source.return_value = "user"
            
            # Mock SelectComponent
            async def mock_show(**kwargs):
                return "gpt-4"
            
            mock_select = MagicMock()
            mock_select.show = mock_show
            
            with patch('eflycode.cli.components.model_list.ConfigManager') as mock_cm_class:
                mock_cm_class.get_instance.return_value = mock_config_manager
                with patch('eflycode.cli.components.model_list.SelectComponent', return_value=mock_select):
                    component = ModelListComponent()
                    result = await component.show()
                    self.assertEqual(result, "gpt-4")
        
        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()

