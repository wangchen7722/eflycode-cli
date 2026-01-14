"""Skills 模块

提供技能系统功能，包括：
- 技能发现和加载
- 技能管理
- 技能激活工具
- Skills Advisor
"""

# 导入公共接口
from eflycode.core.skills.activate_tool import ActivateSkillTool
from eflycode.core.skills.loader import SkillLoader, parse_frontmatter
from eflycode.core.skills.manager import SkillsManager
from eflycode.core.skills.models import (
    SkillChanges,
    SkillManifest,
    SkillManifestEntry,
    SkillMetadata,
)
from eflycode.core.skills.skills_advisor import SkillsAdvisor

__all__ = [
    # 模型
    "SkillMetadata",
    "SkillManifest",
    "SkillManifestEntry",
    "SkillChanges",
    # 加载器
    "SkillLoader",
    "parse_frontmatter",
    # 管理器
    "SkillsManager",
    # 工具和 Advisor
    "ActivateSkillTool",
    "SkillsAdvisor",
]
