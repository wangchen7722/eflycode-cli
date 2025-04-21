from pathlib import Path
from typing import List, Optional

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, TemplateNotFound


class PromptLoader:
    """提示词加载器，负责加载和渲染jinja2模板"""
    _instance: Optional["PromptLoader"] = None
    _prompt_dirs: List[Path] = []

    def __new__(cls, prompt_dir: Optional[Path] = None) -> "PromptLoader":
        """实现单例模式
        
        Args:
            prompt_dir: 提示词模板目录路径
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, prompt_dir: Optional[Path] = None):
        """初始化提示词加载器
        
        Args:
            prompt_dir: 提示词模板目录路径
        """
        if getattr(self, '_initialized', False):
            return
        if prompt_dir:
            self.add_prompt_dir(prompt_dir)
        self._init_env()
        self._initialized = True

    @classmethod
    def get_instance(cls) -> "PromptLoader":
        """获取PromptLoader全局唯一实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def add_prompt_dir(cls, prompt_dir: Path) -> None:
        """添加提示词模板目录
        
        Args:
            prompt_dir: 提示词模板目录路径
        """
        if prompt_dir not in cls._prompt_dirs:
            cls._prompt_dirs.append(prompt_dir)
            if cls._instance:
                cls._instance._init_env()

    def _init_env(self) -> None:
        """初始化jinja2模板环境"""
        loaders = [FileSystemLoader(str(path)) for path in self._prompt_dirs]
        self.env = Environment(
            loader=ChoiceLoader(loaders),
            trim_blocks=True,
            lstrip_blocks=True
        )

    def render_template(self, template_path: str, **kwargs) -> str:
        """加载并渲染指定模板
        
        Args:
            template_path: 模板文件相对路径
            **kwargs: 传递给模板的渲染参数
            
        Returns:
            渲染后的文本内容
            
        Raises:
            PromptNotFoundError: 当指定的模板文件不存在时
            PromptRenderError: 当模板渲染失败时
        """
        try:
            template = self.env.get_template(template_path)
            return template.render(**kwargs)
        except TemplateNotFound:
            raise
        except Exception:
            raise
