import unittest
from pathlib import Path
from unittest import mock
from jinja2 import TemplateNotFound

from echoai.core.prompt.prompt_loader import PromptLoader


class TestPromptLoader(unittest.TestCase):
    """PromptLoader单元测试"""
    
    def setUp(self):
        """测试前重置PromptLoader的单例状态"""
        PromptLoader._instance = None
        PromptLoader._prompt_dirs = []
        
        # 注意这里的mock路径修改为PromptLoader所在模块的Environment
        self.mock_env_patcher = mock.patch('echoai.core.prompt.prompt_loader.Environment')
        self.mock_env = self.mock_env_patcher.start()
        self.mock_env_instance = mock.MagicMock()
        self.mock_env.return_value = self.mock_env_instance
        
        self.mock_template = mock.MagicMock()
        self.mock_template.render.return_value = "Hello, World!"
    
    def tearDown(self):
        """清理mock"""
        self.mock_env_patcher.stop()
    
    def test_singleton_pattern(self):
        """测试PromptLoader的单例模式"""
        loader1 = PromptLoader()
        loader2 = PromptLoader()
        self.assertIs(loader1, loader2)
        
        loader3 = PromptLoader.get_instance()
        self.assertIs(loader1, loader3)
    
    def test_add_prompt_dir(self):
        """测试添加提示词目录功能"""
        test_dir = Path("/test/dir")
        loader = PromptLoader(test_dir)
        self.assertIn(test_dir, PromptLoader._prompt_dirs)
        
        another_dir = Path("/another/dir")
        PromptLoader.add_prompt_dir(another_dir)
        self.assertIn(another_dir, PromptLoader._prompt_dirs)

    def test_render_template(self):
        """测试渲染模板功能"""
        # 设置mock模板返回值
        self.mock_env_instance.get_template.return_value = self.mock_template
        
        # 创建测试目录路径
        test_dir = Path("/test/dir")
        loader = PromptLoader(test_dir)
        
        # 测试模板渲染
        template_name = "test.prompt"
        # 不再转换为Path对象，直接使用模板名称
        template_vars = {"name": "World"}
        result = loader.render_template(template_name, **template_vars)
        
        # 验证结果
        self.assertEqual(result, "Hello, World!")
        # 验证模板加载调用
        self.mock_env_instance.get_template.assert_called_once_with(template_name)
        # 验证模板渲染调用
        self.mock_template.render.assert_called_once_with(**template_vars)
    
    def test_template_not_found(self):
        """测试模板不存在的异常处理"""
        self.mock_env_instance.get_template.side_effect = TemplateNotFound("test.prompt")
        
        loader = PromptLoader(Path("/test/dir"))
        with self.assertRaises(TemplateNotFound):
            loader.render_template("test.prompt", name="World")
    
    def test_render_error(self):
        """测试渲染错误的异常处理"""
        self.mock_env_instance.get_template.return_value = self.mock_template
        self.mock_template.render.side_effect = Exception("Render error")
        
        loader = PromptLoader(Path("/test/dir"))
        with self.assertRaises(Exception):
            loader.render_template("test.prompt", name="World")


if __name__ == '__main__':
    unittest.main()