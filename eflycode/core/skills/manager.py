"""技能管理器

负责管理技能清单，提供技能查询和操作接口
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from eflycode.core.constants import EFLYCODE_DIR, SKILLS_DIR, SKILLS_MANIFEST_FILE
from eflycode.core.skills.loader import SkillLoader
from eflycode.core.skills.models import SkillChanges, SkillManifest, SkillMetadata
from eflycode.core.utils.logger import logger


class SkillsManager:
    """技能管理器（单例）

    管理技能清单，提供技能查询、启用/禁用等功能
    """

    _instance: Optional["SkillsManager"] = None

    def __init__(self):
        """初始化技能管理器"""
        if SkillsManager._instance is not None:
            raise RuntimeError("SkillsManager 是单例，请使用 get_instance() 获取实例")

        self.user_skills_dir: Optional[Path] = None
        self.project_skills_dir: Optional[Path] = None
        self.manifest_file_path: Optional[Path] = None
        self.manifest = SkillManifest()
        self.skills_cache: Dict[str, SkillMetadata] = {}

    @classmethod
    def get_instance(cls) -> "SkillsManager":
        """获取单例实例

        Returns:
            SkillsManager: 单例实例
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例实例（主要用于测试）"""
        cls._instance = None

    def initialize(
        self,
        user_config_dir: Path,
        project_workspace_dir: Optional[Path] = None,
    ) -> None:
        """初始化技能管理器

        Args:
            user_config_dir: 用户配置目录 (~/.eflycode)
            project_workspace_dir: 项目工作区目录（可选）
        """
        self.user_skills_dir = user_config_dir / SKILLS_DIR
        self.manifest_file_path = user_config_dir / SKILLS_MANIFEST_FILE

        if project_workspace_dir:
            self.project_skills_dir = project_workspace_dir / EFLYCODE_DIR / SKILLS_DIR
        else:
            self.project_skills_dir = None

        # 创建技能目录（如果不存在）
        self.user_skills_dir.mkdir(parents=True, exist_ok=True)
        if self.project_skills_dir:
            self.project_skills_dir.mkdir(parents=True, exist_ok=True)

        # 加载清单文件
        self._load_manifest()

        # 重新扫描技能
        self.reload_skills()

    def _load_manifest(self) -> None:
        """从文件加载清单"""
        if not self.manifest_file_path or not self.manifest_file_path.exists():
            logger.debug("技能清单文件不存在，使用空清单")
            self.manifest = SkillManifest()
            return

        try:
            with open(self.manifest_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.manifest = SkillManifest.model_validate(data)
            logger.debug(f"加载技能清单，共 {len(self.manifest.skills)} 个技能")
        except Exception as e:
            logger.warning(f"加载技能清单失败: {e}，使用空清单")
            self.manifest = SkillManifest()

    def _save_manifest(self) -> None:
        """保存清单到文件"""
        if not self.manifest_file_path:
            logger.warning("清单文件路径未设置，跳过保存")
            return

        try:
            with open(self.manifest_file_path, "w", encoding="utf-8") as f:
                json.dump(self.manifest.model_dump(), f, ensure_ascii=False, indent=2)
            logger.debug(f"保存技能清单，共 {len(self.manifest.skills)} 个技能")
        except Exception as e:
            logger.error(f"保存技能清单失败: {e}")

    def reload_skills(self) -> SkillChanges:
        """重新扫描技能目录并更新清单

        Returns:
            SkillChanges: 变更记录
        """
        loader = SkillLoader(
            user_skills_dir=self.user_skills_dir,
            project_skills_dir=self.project_skills_dir,
        )

        # 扫描所有技能
        new_skills = loader.scan_skills(old_manifest=self.manifest)

        # 检测变更
        changes = loader.detect_changes(new_skills, old_manifest=self.manifest)

        if changes.has_changes:
            # 更新清单
            old_manifest = self.manifest
            self.manifest = SkillManifest()
            for skill in new_skills.values():
                # 从旧清单中恢复 disabled 状态
                old_entry = old_manifest.skills.get(skill.name)
                if old_entry and old_entry.disabled:
                    skill.disabled = True
                self.manifest.add_skill(skill)

            # 保存清单
            self._save_manifest()

            # 输出日志
            if changes.added:
                added_names = [s.name for s in changes.added]
                logger.info(f"新增技能: {', '.join(added_names)}")
            if changes.modified:
                modified_names = [s.name for s in changes.modified]
                logger.info(f"修改技能: {', '.join(modified_names)}")
            if changes.removed:
                removed_names = [s.name for s in changes.removed]
                logger.info(f"删除技能: {', '.join(removed_names)}")
        else:
            logger.debug("无技能变更")
            # 即使没有变更，也需要从清单中恢复 disabled 状态
            for skill in new_skills.values():
                old_entry = self.manifest.skills.get(skill.name)
                if old_entry and old_entry.disabled:
                    skill.disabled = True

        # 更新缓存
        self.skills_cache = new_skills

        return changes

    def get_enabled_skills(self) -> List[SkillMetadata]:
        """获取所有启用的技能

        Returns:
            List[SkillMetadata]: 启用的技能列表
        """
        return [
            skill
            for skill in self.skills_cache.values()
            if not skill.disabled
        ]

    def get_all_skills(self) -> List[SkillMetadata]:
        """获取所有技能（包括禁用的）

        Returns:
            List[SkillMetadata]: 所有技能列表
        """
        return list(self.skills_cache.values())

    def get_skill_by_name(self, name: str) -> Optional[SkillMetadata]:
        """根据名称获取技能

        Args:
            name: 技能名称

        Returns:
            Optional[SkillMetadata]: 技能元数据，如果不存在返回 None
        """
        return self.skills_cache.get(name)

    def enable_skill(self, name: str) -> bool:
        """启用技能

        Args:
            name: 技能名称

        Returns:
            bool: 是否成功启用
        """
        if name not in self.skills_cache:
            logger.warning(f"技能不存在: {name}")
            return False

        skill = self.skills_cache[name]
        if not skill.disabled:
            logger.debug(f"技能已启用: {name}")
            return True

        skill.disabled = False
        self.manifest.add_skill(skill)
        self._save_manifest()
        logger.info(f"启用技能: {name}")
        return True

    def disable_skill(self, name: str) -> bool:
        """禁用技能

        Args:
            name: 技能名称

        Returns:
            bool: 是否成功禁用
        """
        if name not in self.skills_cache:
            logger.warning(f"技能不存在: {name}")
            return False

        skill = self.skills_cache[name]
        if skill.disabled:
            logger.debug(f"技能已禁用: {name}")
            return True

        skill.disabled = True
        self.manifest.add_skill(skill)
        self._save_manifest()
        logger.info(f"禁用技能: {name}")
        return True

    def get_available_skills_for_prompt(self) -> List[dict]:
        """获取用于系统提示词的可用技能列表

        Returns:
            List[dict]: 技能列表，每个元素包含 name, description, location
        """
        enabled_skills = self.get_enabled_skills()
        return [
            {
                "name": skill.name,
                "description": skill.description,
                "location": str(skill.file_path),
            }
            for skill in enabled_skills
        ]

    def get_skill_content(self, name: str) -> Optional[str]:
        """获取技能内容

        用于 activate_skill 工具返回完整的技能内容

        Args:
            name: 技能名称

        Returns:
            Optional[str]: 技能内容，如果不存在返回 None
        """
        skill = self.get_skill_by_name(name)
        if not skill:
            return None
        return skill.content
