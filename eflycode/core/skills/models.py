"""Skills 数据模型

定义技能相关的数据结构
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class SkillMetadata(BaseModel):
    """技能元数据

    包含技能的基本信息和内容
    """

    name: str = Field(..., description="技能名称（从文件名提取）")
    description: str = Field(..., description="技能描述（从 frontmatter 解析）")
    content: str = Field(..., description="技能 Markdown 正文内容")
    file_path: Path = Field(..., description="技能文件路径")
    source: Literal["user", "project"] = Field(..., description="技能来源")
    disabled: bool = Field(default=False, description="是否禁用")
    mtime: float = Field(..., description="文件修改时间（Unix 时间戳）")

    def __hash__(self) -> int:
        """使技能可以用于集合操作"""
        return hash((self.name, self.source, self.file_path))

    def __eq__(self, other: object) -> bool:
        """技能相等性判断"""
        if not isinstance(other, SkillMetadata):
            return False
        return (
            self.name == other.name
            and self.source == other.source
            and self.file_path == other.file_path
        )


class SkillManifestEntry(BaseModel):
    """清单文件中的技能条目"""

    name: str = Field(..., description="技能名称")
    description: str = Field(..., description="技能描述")
    file_path: str = Field(..., description="技能文件路径")
    disabled: bool = Field(default=False, description="是否禁用")
    mtime: float = Field(..., description="文件修改时间")


class SkillManifest(BaseModel):
    """技能清单

    存储所有已发现的技能信息
    """

    skills: Dict[str, SkillManifestEntry] = Field(
        default_factory=dict, description="技能清单，key 为技能名称"
    )

    def add_skill(self, skill: SkillMetadata) -> None:
        """添加或更新技能到清单

        Args:
            skill: 技能元数据
        """
        self.skills[skill.name] = SkillManifestEntry(
            name=skill.name,
            description=skill.description,
            file_path=str(skill.file_path),
            disabled=skill.disabled,
            mtime=skill.mtime,
        )

    def remove_skill(self, name: str) -> bool:
        """从清单中移除技能

        Args:
            name: 技能名称

        Returns:
            bool: 是否成功移除
        """
        if name in self.skills:
            del self.skills[name]
            return True
        return False

    def get_skill(self, name: str) -> Optional[SkillManifestEntry]:
        """获取技能条目

        Args:
            name: 技能名称

        Returns:
            Optional[SkillManifestEntry]: 技能条目，如果不存在返回 None
        """
        return self.skills.get(name)

    def get_enabled_skills(self) -> List[SkillManifestEntry]:
        """获取所有启用的技能

        Returns:
            List[SkillManifestEntry]: 启用的技能列表
        """
        return [skill for skill in self.skills.values() if not skill.disabled]


class SkillChanges(BaseModel):
    """技能变更记录

    记录技能的增删改情况
    """

    added: List[SkillMetadata] = Field(default_factory=list, description="新增的技能")
    modified: List[SkillMetadata] = Field(default_factory=list, description="修改的技能")
    removed: List[SkillManifestEntry] = Field(
        default_factory=list, description="删除的技能（旧清单条目）"
    )

    @property
    def has_changes(self) -> bool:
        """是否有变更

        Returns:
            bool: 如果有任何变更返回 True
        """
        return bool(self.added or self.modified or self.removed)
