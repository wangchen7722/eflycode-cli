"""激活技能工具

提供 activate_skill 工具，用于激活指定的技能
"""

from typing import Annotated, List

from eflycode.core.llm.protocol import ToolFunctionParameters
from eflycode.core.skills.manager import SkillsManager
from eflycode.core.tool.base import BaseTool, ToolType
from eflycode.core.utils.logger import logger


class ActivateSkillTool(BaseTool):
    """激活技能工具

    用于激活指定的技能，获取技能的完整指令内容
    """

    def __init__(self):
        """初始化激活技能工具"""
        super().__init__()
        self._manager: SkillsManager = SkillsManager.get_instance()

    @property
    def name(self) -> str:
        return "activate_skill"

    @property
    def type(self) -> str:
        return ToolType.FUNCTION

    @property
    def permission(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        # 动态生成描述，包含可用技能列表
        enabled_skills = self._manager.get_enabled_skills()
        if not enabled_skills:
            return "激活技能工具。当前没有可用的技能。"

        skill_list = ", ".join([f'"{s.name}"' for s in enabled_skills])
        return (
            f"激活技能工具，用于激活指定的技能并获取技能指令。"
            f"可用技能：{skill_list}。"
            f"激活后，请严格优先遵循返回的 <activated_skill> 中的指令。"
        )

    def _get_enum_values(self) -> List[str]:
        """获取可用的技能名称列表

        Returns:
            List[str]: 技能名称列表
        """
        enabled_skills = self._manager.get_enabled_skills()
        return [skill.name for skill in enabled_skills]

    @property
    def parameters(self) -> ToolFunctionParameters:
        enum_values = self._get_enum_values()

        if not enum_values:
            # 没有可用技能时，参数为 string 类型
            return ToolFunctionParameters(
                type="object",
                properties={
                    "skill_name": {
                        "type": "string",
                        "description": "要激活的技能名称（当前没有可用的技能）",
                    },
                },
                required=["skill_name"],
            )

        return ToolFunctionParameters(
            type="object",
            properties={
                "skill_name": {
                    "type": "string",
                    "enum": enum_values,
                    "description": "要激活的技能名称",
                },
            },
            required=["skill_name"],
        )

    def do_run(
        self,
        skill_name: Annotated[str, "要激活的技能名称"],
    ) -> str:
        """执行激活技能工具

        Args:
            skill_name: 要激活的技能名称

        Returns:
            str: <activated_skill> XML 格式的技能内容
        """
        # 获取技能元数据
        skill = self._manager.get_skill_by_name(skill_name)
        if not skill:
            logger.warning(f"技能不存在: {skill_name}")
            return f"错误：技能 '{skill_name}' 不存在。"

        # 检查技能是否已禁用
        if skill.disabled:
            logger.warning(f"尝试激活已禁用的技能: {skill_name}")
            return f"错误：技能 '{skill_name}' 已禁用。"

        # 获取技能内容
        content = self._manager.get_skill_content(skill_name)
        if content is None:
            logger.warning(f"无法获取技能内容: {skill_name}")
            return f"错误：无法获取技能 '{skill_name}' 的内容。"

        # 生成 <activated_skill> XML 格式
        result = f'<activated_skill name="{skill_name}">\n'
        result += f"  <instructions>\n"
        result += f"    {self._escape_xml(content)}\n"
        result += f"  </instructions>\n"
        result += f"  <location>{skill.file_path}</location>\n"
        result += f"</activated_skill>"

        logger.info(f"激活技能: {skill_name}")
        return result

    def _escape_xml(self, text: str) -> str:
        """转义 XML 特殊字符

        Args:
            text: 原始文本

        Returns:
            str: 转义后的文本
        """
        # 简单的转义，处理 <, >, &, ", '
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace('"', "&quot;")
        text = text.replace("'", "&apos;")
        return text
