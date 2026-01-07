"""提示词加载器模块

负责加载和渲染系统提示词模板
"""

from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Template, TemplateError, UndefinedError, StrictUndefined

from eflycode.core.utils.logger import logger


class PromptLoader:
    """提示词加载器，负责加载和渲染提示词模板"""

    _instance: Optional["PromptLoader"] = None

    def __init__(self):
        """初始化提示词加载器"""
        pass

    @classmethod
    def get_instance(cls) -> "PromptLoader":
        """获取单例实例

        Returns:
            PromptLoader: 单例实例
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_template(
        self, agent_role: str, workspace_dir: Optional[Path] = None
    ) -> Optional[str]:
        """加载提示词模板

        加载优先级：
        1. 用户配置：.eflycode/agents/{agent_role}/system.prompt
        2. 内置配置：eflycode/core/prompt/agents/{agent_role}/system.prompt
        3. 默认配置：eflycode/core/prompt/agents/default/system.prompt

        Args:
            agent_role: Agent 角色名称
            workspace_dir: 工作区目录

        Returns:
            Optional[str]: 模板内容，如果都不存在返回 None
        """
        # 尝试加载用户配置
        if workspace_dir:
            user_prompt_path = workspace_dir / ".eflycode" / "agents" / agent_role / "system.prompt"
            if user_prompt_path.exists():
                try:
                    template_content = user_prompt_path.read_text(encoding="utf-8")
                    logger.debug(f"加载用户配置提示词: {user_prompt_path}")
                    return template_content
                except Exception as e:
                    logger.warning(f"读取用户配置提示词失败: {user_prompt_path}，错误: {e}")

        # 尝试加载内置配置
        core_prompt_dir = Path(__file__).parent / "agents" / agent_role
        builtin_prompt_path = core_prompt_dir / "system.prompt"
        if builtin_prompt_path.exists():
            try:
                template_content = builtin_prompt_path.read_text(encoding="utf-8")
                logger.debug(f"加载内置提示词: {builtin_prompt_path}")
                return template_content
            except Exception as e:
                logger.warning(f"读取内置提示词失败: {builtin_prompt_path}，错误: {e}")

        # 使用默认配置
        default_prompt_path = Path(__file__).parent / "agents" / "default" / "system.prompt"
        if default_prompt_path.exists():
            try:
                template_content = default_prompt_path.read_text(encoding="utf-8")
                logger.debug(f"加载默认提示词: {default_prompt_path}")
                return template_content
            except Exception as e:
                logger.warning(f"读取默认提示词失败: {default_prompt_path}，错误: {e}")

        logger.warning(f"未找到提示词模板，agent_role: {agent_role}")
        return None

    def render(self, template: str, variables: Dict[str, Any]) -> str:
        """渲染模板

        Args:
            template: 模板内容
            variables: 变量字典

        Returns:
            str: 渲染后的内容，如果渲染失败返回空字符串
        """
        try:
            jinja_template = Template(template, undefined=StrictUndefined)
            return jinja_template.render(**variables)
        except UndefinedError as e:
            logger.warning(f"模板渲染失败，未定义变量: {e}")
            return ""
        except TemplateError as e:
            logger.warning(f"模板渲染失败，模板错误: {e}")
            return ""
        except Exception as e:
            logger.warning(f"模板渲染失败，未知错误: {e}")
            return ""

