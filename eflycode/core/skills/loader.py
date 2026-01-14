"""技能加载器

负责扫描和解析技能文件
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from eflycode.core.skills.models import SkillChanges, SkillManifest, SkillMetadata
from eflycode.core.utils.logger import logger


# Frontmatter 解析正则
# 匹配 --- 开头，中间内容（可为空），--- 结尾，后面跟换行
FRONTMATTER_PATTERN = re.compile(r"\A---\r?\n([\s\S]*?)\r?\n?---\r?\n([\s\S]*)")


def parse_frontmatter(content: str) -> Tuple[Optional[dict], str]:
    """解析 Markdown 文件的 YAML frontmatter

    Args:
        content: Markdown 文件内容

    Returns:
        Tuple[Optional[dict], str]: (frontmatter 字典, 正文内容)
            如果没有 frontmatter，返回 (None, 原始内容)
    """
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        return None, content

    frontmatter_text, body = match.groups()

    try:
        frontmatter = yaml.safe_load(frontmatter_text)
        # 空的 frontmatter（如 ---）会被解析为 None
        if frontmatter is None:
            frontmatter = {}
        if not isinstance(frontmatter, dict):
            logger.warning(f"Frontmatter 不是字典类型: {type(frontmatter)}")
            return None, content
        return frontmatter, body.strip()
    except yaml.YAMLError as e:
        logger.warning(f"Frontmatter YAML 解析失败: {e}")
        return None, content


class SkillLoader:
    """技能加载器

    扫描用户和项目技能目录，解析技能文件
    """

    def __init__(
        self,
        user_skills_dir: Optional[Path] = None,
        project_skills_dir: Optional[Path] = None,
    ):
        """初始化技能加载器

        Args:
            user_skills_dir: 用户技能目录 (~/.eflycode/skills)
            project_skills_dir: 项目技能目录 (<project>/.eflycode/skills)
        """
        self.user_skills_dir = user_skills_dir
        self.project_skills_dir = project_skills_dir

    def _scan_directory(self, dir_path: Path, source: str) -> List[SkillMetadata]:
        """扫描单个技能目录

        Args:
            dir_path: 目录路径
            source: 来源标识 ("user" 或 "project")

        Returns:
            List[SkillMetadata]: 找到的技能列表
        """
        if not dir_path or not dir_path.exists():
            logger.debug(f"技能目录不存在: {dir_path}")
            return []

        if not dir_path.is_dir():
            logger.warning(f"技能路径不是目录: {dir_path}")
            return []

        skills = []

        # 扫描所有 .md 文件
        for file_path in dir_path.glob("*.md"):
            try:
                # 读取文件内容
                content = file_path.read_text(encoding="utf-8")

                # 解析 frontmatter
                frontmatter, body = parse_frontmatter(content)

                # 检查是否有 description
                if not frontmatter or "description" not in frontmatter:
                    logger.warning(
                        f"技能文件缺少 description，跳过: {file_path}"
                    )
                    continue

                description = frontmatter["description"]
                if not isinstance(description, str) or not description.strip():
                    logger.warning(
                        f"技能 description 不是有效字符串，跳过: {file_path}"
                    )
                    continue

                # 提取技能名称（文件名去掉 .md 扩展名）
                name = file_path.stem

                # 获取文件修改时间
                mtime = file_path.stat().st_mtime

                skill = SkillMetadata(
                    name=name,
                    description=description.strip(),
                    content=body,
                    file_path=file_path,
                    source=source,  # type: ignore
                    mtime=mtime,
                )

                skills.append(skill)
                logger.debug(f"加载技能: {name} from {file_path}")

            except Exception as e:
                logger.error(f"读取技能文件失败: {file_path}, 错误: {e}")

        return skills

    def scan_skills(self, old_manifest: Optional[SkillManifest] = None) -> Dict[str, SkillMetadata]:
        """扫描所有技能目录

        按照优先级合并：项目技能覆盖同名用户技能

        Args:
            old_manifest: 旧的技能清单，用于变更检测

        Returns:
            Dict[str, SkillMetadata]: 技能字典，key 为技能名称
        """
        # 先扫描用户技能
        user_skills: Dict[str, SkillMetadata] = {}
        if self.user_skills_dir:
            for skill in self._scan_directory(self.user_skills_dir, "user"):
                user_skills[skill.name] = skill

        # 再扫描项目技能，覆盖同名的用户技能
        all_skills = user_skills.copy()
        if self.project_skills_dir:
            for skill in self._scan_directory(self.project_skills_dir, "project"):
                if skill.name in all_skills:
                    logger.debug(
                        f"项目技能覆盖用户技能: {skill.name} "
                        f"({all_skills[skill.name].source} -> {skill.source})"
                    )
                all_skills[skill.name] = skill

        logger.info(f"扫描完成，共发现 {len(all_skills)} 个技能")
        return all_skills

    def detect_changes(
        self,
        new_skills: Dict[str, SkillMetadata],
        old_manifest: Optional[SkillManifest] = None,
    ) -> SkillChanges:
        """检测技能变更

        Args:
            new_skills: 新扫描的技能字典
            old_manifest: 旧的技能清单

        Returns:
            SkillChanges: 变更记录
        """
        changes = SkillChanges()

        if not old_manifest:
            # 没有旧清单，所有技能都是新增的
            changes.added = list(new_skills.values())
            return changes

        old_skills_map = old_manifest.skills

        # 检测新增和修改的技能
        for name, new_skill in new_skills.items():
            if name not in old_skills_map:
                # 新增技能
                changes.added.append(new_skill)
                logger.debug(f"新增技能: {name}")
            else:
                old_entry = old_skills_map[name]
                # 检测是否有变更（通过 mtime 和 description）
                if (
                    new_skill.mtime != old_entry.mtime
                    or new_skill.description != old_entry.description
                ):
                    # 修改的技能
                    changes.modified.append(new_skill)
                    logger.debug(f"修改技能: {name}")

        # 检测删除的技能
        for name, old_entry in old_skills_map.items():
            if name not in new_skills:
                changes.removed.append(old_entry)
                logger.debug(f"删除技能: {name}")

        return changes
