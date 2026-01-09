"""配置管理模块

负责查找和加载配置文件，支持从项目目录或用户目录读取配置
"""

import datetime
import os
import platform
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from eflycode.core.constants import (
    DEFAULT_SYSTEM_VERSION,
    EFLYCODE_DIR,
    CONFIG_FILE,
    WORKSPACE_SEARCH_MAX_DEPTH,
)
from eflycode.core.context.strategies import ContextStrategyConfig
from eflycode.core.llm.protocol import DEFAULT_MAX_CONTEXT_LENGTH, LLMConfig
from eflycode.core.utils.logger import logger


class Config:
    """配置类，包含模型配置和工作区信息"""

    def __init__(
        self,
        model_config: LLMConfig,
        model_name: str,
        workspace_dir: Path,
        config_file_path: Optional[Path] = None,
        context_config: Optional[ContextStrategyConfig] = None,
        checkpointing_enabled: bool = False,
        source: str = "default",
    ):
        """初始化配置

        Args:
            model_config: LLM 配置
            model_name: 模型名称
            workspace_dir: 工作区根目录
            config_file_path: 配置文件路径，如果是从文件加载的
            context_config: 上下文管理配置
            checkpointing_enabled: 是否启用 checkpointing
            source: 配置来源，"user"、"project" 或 "default"，TODO: 未来支持 "team" 作为配置来源
        """
        self.model_config = model_config
        self.model_name = model_name
        self.workspace_dir = workspace_dir
        self.config_file_path = config_file_path
        self.context_config = context_config
        self.checkpointing_enabled = checkpointing_enabled
        # source 只能是 "user", "project", "default" 之一
        # TODO: 支持 "team" 作为配置来源
        if source not in ("user", "project", "default"):
            raise ValueError(f"无效的配置来源: {source}，必须是 'user', 'project' 或 'default'")
        self.source = source


def _merge_entries_by_key(
    base_entries: List[Dict[str, Any]],
    override_entries: List[Dict[str, Any]],
    key: str = "model",
) -> List[Dict[str, Any]]:
    """按指定 key 字段合并列表

    相同 key 的条目会被覆盖，不同 key 的条目会保留

    Args:
        base_entries: 基础列表，用户配置
        override_entries: 覆盖列表，项目配置
        key: 用于识别条目的字段名，默认为 "model"

    Returns:
        List[Dict[str, Any]]: 合并后的列表
    """
    # 使用字典保持顺序并便于查找
    merged = {}

    # 先添加基础配置的条目
    for entry in base_entries:
        if isinstance(entry, dict) and key in entry:
            merged[entry[key]] = entry.copy()

    # 用覆盖配置的条目覆盖或添加
    for entry in override_entries:
        if isinstance(entry, dict) and key in entry:
            if entry[key] in merged:
                # 合并同一个 key 的条目
                merged[entry[key]].update(entry)
            else:
                merged[entry[key]] = entry.copy()

    return list(merged.values())


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """深度合并两个配置字典

    合并策略：
    - 字典：递归合并
    - 列表：按 model 字段智能合并
    - 其他类型：override 覆盖 base

    Args:
        base: 基础配置字典，用户配置
        override: 覆盖配置字典，项目配置

    Returns:
        Dict[str, Any]: 合并后的配置字典
    """
    result = base.copy()

    for key, override_value in override.items():
        if key not in result:
            # 基础配置没有此键，直接使用覆盖值
            result[key] = override_value
        elif isinstance(result[key], dict) and isinstance(override_value, dict):
            # 两者都是字典，递归合并
            result[key] = _deep_merge(result[key], override_value)
        elif (
            key == "entries"
            and isinstance(result[key], list)
            and isinstance(override_value, list)
        ):
            # entries 列表按 model 字段智能合并
            result[key] = _merge_entries_by_key(result[key], override_value, "model")
        else:
            # 其他情况，覆盖值直接覆盖
            result[key] = override_value

    return result


def resolve_workspace_dir() -> Path:
    """解析工作区目录

    从当前目录向上查找含有 .eflycode 目录的路径

    查找逻辑：
    1. 从当前目录开始向上查找
    2. 找到含有 .eflycode 目录的路径即为工作区目录
    3. 最多向上查找 3 级目录
    4. 如果找不到，返回当前执行路径

    Returns:
        Path: 工作区目录路径
    """
    initial_cwd = Path.cwd().resolve()
    current_dir = initial_cwd
    user_home = Path.home().resolve()

    for _ in range(WORKSPACE_SEARCH_MAX_DEPTH):  # 向上最多查找指定级数
        eflycode_dir = current_dir / EFLYCODE_DIR
        # 检查是否存在 .eflycode 目录，且不是用户目录
        if eflycode_dir.is_dir() and current_dir != user_home:
            return current_dir
        if current_dir.parent == current_dir:
            break
        current_dir = current_dir.parent

    # 找不到时返回当前执行路径
    return initial_cwd


def get_user_config_dir() -> Path:
    """获取用户配置目录

    Returns:
        Path: 用户配置目录路径 (~/.eflycode)
    """
    return Path.home() / EFLYCODE_DIR


def find_config_files() -> tuple[Optional[Path], Optional[Path], Optional[Path]]:
    """查找配置文件

    查找逻辑：
    1. 先查找用户目录 ~/.eflycode/config.yaml 作为基础配置
    2. 从当前目录开始，向上查找含有 .eflycode 目录的路径作为项目配置
    3. 项目配置会与用户配置合并，项目配置优先

    Returns:
        tuple[Optional[Path], Optional[Path], Optional[Path]]: 
            (用户配置路径, 项目配置路径, 工作区目录)
    """
    # 1. 查找用户目录配置
    user_config_dir = get_user_config_dir()
    user_config_path = user_config_dir / CONFIG_FILE
    if not (user_config_path.exists() and user_config_path.is_file()):
        user_config_path = None

    # 2. 查找项目目录配置
    workspace_dir = resolve_workspace_dir()
    project_config_path = None

    config_path = workspace_dir / EFLYCODE_DIR / CONFIG_FILE
    if config_path.exists() and config_path.is_file():
        project_config_path = config_path

    return user_config_path, project_config_path, workspace_dir


def load_config_from_file(config_path: Path) -> dict:
    """从 YAML 文件加载配置

    Args:
        config_path: 配置文件路径

    Returns:
        dict: 配置字典

    Raises:
        FileNotFoundError: 如果文件不存在
        yaml.YAMLError: 如果 YAML 解析失败
    """
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def parse_model_config(config_data: dict) -> LLMConfig:
    """解析模型配置

    Args:
        config_data: 配置字典

    Returns:
        LLMConfig: LLM 配置对象
    """
    model_section = config_data.get("model", {})
    
    # 获取默认模型配置
    default_model = model_section.get("default", "")
    
    # 查找对应的模型条目
    model_entry = None
    entries = model_section.get("entries", [])
    if isinstance(entries, list):
        for entry in entries:
            if entry.get("model") == default_model:
                model_entry = entry
                break
    
    # 如果没有找到，使用第一个条目
    if not model_entry and entries:
        model_entry = entries[0] if isinstance(entries, list) else entries
    
    # 如果还是没有，使用默认值
    if not model_entry:
        model_entry = {}
    
    # 从环境变量或配置中获取 API Key
    api_key = (
        os.getenv("OPENAI_API_KEY")
        or model_entry.get("api_key")
        or os.getenv("EFLYCODE_API_KEY")
    )
    
    return LLMConfig(
        api_key=api_key,
        base_url=model_entry.get("base_url"),
        timeout=60.0,
        max_retries=3,
        temperature=model_entry.get("temperature"),
        max_tokens=model_entry.get("max_tokens"),
    )


def get_model_name_from_config(config_data: dict) -> str:
    """从配置中获取模型名称

    Args:
        config_data: 配置字典

    Returns:
        str: 模型名称
    """
    model_section = config_data.get("model", {})
    default_model = model_section.get("default", "")
    
    if default_model:
        return default_model
    
    # 如果没有默认模型，使用第一个条目的模型
    entries = model_section.get("entries", [])
    if isinstance(entries, list) and entries:
        return entries[0].get("model", "gpt-4")
    
    return "gpt-4"


def parse_context_config(config_data: dict) -> Optional[ContextStrategyConfig]:
    """解析上下文管理配置

    Args:
        config_data: 配置字典

    Returns:
        Optional[ContextStrategyConfig]: 上下文策略配置，如果未配置则返回 None
    """
    context_section = config_data.get("context")
    if not context_section:
        return None

    strategy_type = context_section.get("strategy", "summary")
    summary_section = context_section.get("summary", {})
    sliding_window_section = context_section.get("sliding_window", {})

    return ContextStrategyConfig(
        strategy_type=strategy_type,
        summary_threshold=summary_section.get("threshold", 0.8),
        summary_keep_recent=summary_section.get("keep_recent", 10),
        summary_model=summary_section.get("model"),
        sliding_window_size=sliding_window_section.get("size", 10),
    )


def get_max_context_length(config_data: dict) -> int:
    """从配置中获取模型的最大上下文长度

    Args:
        config_data: 配置字典

    Returns:
        int: 最大上下文长度，如果未配置则返回默认值
    """
    model_section = config_data.get("model", {})
    default_model = model_section.get("default", "")
    
    entries = model_section.get("entries", [])
    if isinstance(entries, list):
        for entry in entries:
            if entry.get("model") == default_model:
                return entry.get("max_context_length", DEFAULT_MAX_CONTEXT_LENGTH)
        if entries:
            return entries[0].get("max_context_length", DEFAULT_MAX_CONTEXT_LENGTH)
    
    return DEFAULT_MAX_CONTEXT_LENGTH


def get_checkpointing_enabled(config_data: dict) -> bool:
    """从配置中获取 checkpointing 开关"""
    checkpointing_section = config_data.get("checkpointing", {})
    if isinstance(checkpointing_section, dict):
        return bool(checkpointing_section.get("enabled", False))
    return False


class ConfigManager:
    """全局配置管理器单例

    提供系统信息、工作区信息、时间信息等静态环境信息的访问接口
    支持懒加载配置，首次访问时自动加载
    """

    _instance: Optional["ConfigManager"] = None

    def __init__(self):
        """初始化配置管理器"""
        self.config: Optional[Config] = None
        self._system_version: Optional[str] = None
        self._initialized: bool = False

    @classmethod
    def get_instance(cls) -> "ConfigManager":
        """获取单例实例

        Returns:
            ConfigManager: 单例实例
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_config(self) -> Config:
        """内部方法：加载配置

        配置加载和合并逻辑：
        1. 先加载用户目录配置 (~/.eflycode/config.yaml) 作为基础
        2. 再加载项目目录配置并与用户配置合并，项目配置优先
        3. 如果都没有，使用默认配置
        
        TODO: 支持 team 配置来源
        - 优先级：team > project > user > default
        - team 配置应该从团队共享配置中加载

        Returns:
            Config: 配置对象，source 属性标识配置来源，"user"、"project" 或 "default"
        """
        user_config_path, project_config_path, workspace_dir = find_config_files()

        # 1. 加载用户配置作为基础
        base_config_data = {}
        if user_config_path:
            try:
                base_config_data = load_config_from_file(user_config_path)
            except Exception as e:
                logger.warning(f"加载用户配置文件失败: {e}")

        # 2. 加载项目配置并合并
        config_data = base_config_data
        config_file_path = user_config_path
        source = "user"  # 默认来源
        
        if project_config_path:
            try:
                project_config_data = load_config_from_file(project_config_path)
                if base_config_data:
                    # 两者都有，合并配置，项目配置优先
                    config_data = _deep_merge(base_config_data, project_config_data)
                    # 合并后的配置来源应该是 project，因为项目配置优先
                    source = "project"
                else:
                    # 只有项目配置
                    config_data = project_config_data
                    source = "project"
                config_file_path = project_config_path  # 使用项目配置路径
            except Exception as e:
                logger.warning(f"加载项目配置文件失败: {e}，使用用户配置")
                source = "user" if base_config_data else "default"
        
        # TODO: 支持 team 配置来源
        # 当实现 team 配置时，优先级应该是：team > project > user > default

        # 3. 如果有配置数据，解析并返回
        if config_data:
            try:
                model_config = parse_model_config(config_data)
                model_name = get_model_name_from_config(config_data)
                context_config = parse_context_config(config_data)
                checkpointing_enabled = get_checkpointing_enabled(config_data)

                return Config(
                    model_config=model_config,
                    model_name=model_name,
                    workspace_dir=workspace_dir,
                    config_file_path=config_file_path,
                    context_config=context_config,
                    checkpointing_enabled=checkpointing_enabled,
                    source=source,
                )
            except Exception as e:
                logger.warning(f"解析配置失败: {e}，使用默认配置")

        # 4. 使用默认配置
        default_workspace = Path.cwd().resolve()
        default_model_config = LLMConfig(
            api_key=os.getenv("OPENAI_API_KEY") or os.getenv("EFLYCODE_API_KEY"),
            base_url=None,
            timeout=60.0,
            max_retries=3,
            temperature=None,
            max_tokens=None,
        )

        return Config(
            model_config=default_model_config,
            model_name="gpt-4",
            workspace_dir=default_workspace,
            config_file_path=None,
            context_config=None,
            checkpointing_enabled=False,
            source="default",
        )

    def load(self) -> Config:
        """显式加载配置

        Returns:
            Config: 配置对象
        """
        self.config = self._load_config()
        self._initialized = True
        return self.config

    def get_config(self) -> Config:
        """获取配置对象，如果未加载则自动加载

        Returns:
            Config: 配置对象
        """
        if not self._initialized or self.config is None:
            self.load()
        return self.config

    def get_max_context_length(self) -> int:
        """获取模型的最大上下文长度

        Returns:
            int: 最大上下文长度，如果未配置则返回默认值
        """
        config = self.get_config()
        if config.config_file_path:
            try:
                config_data = load_config_from_file(config.config_file_path)
                return get_max_context_length(config_data)
            except Exception:
                pass
        return DEFAULT_MAX_CONTEXT_LENGTH

    def _load_version(self) -> str:
        """加载系统版本

        Returns:
            str: 系统版本号
        """
        if self._system_version is not None:
            return self._system_version

        try:
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib

            pyproject_path = Path(__file__).parent.parent.parent.parent / "pyproject.toml"
            if pyproject_path.exists():
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)
                    self._system_version = data.get("project", {}).get("version", DEFAULT_SYSTEM_VERSION)
                    return self._system_version
        except Exception:
            pass

        self._system_version = DEFAULT_SYSTEM_VERSION
        return self._system_version

    def get_system_info(self) -> Dict[str, str]:
        """获取系统信息

        Returns:
            Dict[str, str]: 系统信息字典，包含 version、timezone、date、time、datetime
        """
        now = datetime.datetime.now()
        timezone = datetime.datetime.now(datetime.timezone.utc).astimezone().tzname()

        return {
            "version": self._load_version(),
            "timezone": timezone or "UTC",
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "datetime": now.isoformat(),
        }

    def get_workspace_dir(self) -> Optional[Path]:
        """获取工作区目录

        Returns:
            Optional[Path]: 工作区目录，如果未配置则返回 None
        """
        config = self.get_config()
        if config and config.workspace_dir:
            return config.workspace_dir
        return None

    def get_workspace_info(self) -> Dict[str, str]:
        """获取工作区信息

        Returns:
            Dict[str, str]: 工作区信息字典，包含 path、name
        """
        config = self.get_config()
        if config and config.workspace_dir:
            workspace_dir = config.workspace_dir
            return {
                "path": str(workspace_dir),
                "name": workspace_dir.name,
            }
        return {
            "path": "",
            "name": "",
        }

    def get_time_info(self) -> Dict[str, str]:
        """获取时间信息

        Returns:
            Dict[str, str]: 时间信息字典，包含 timezone、date、time、datetime
        """
        now = datetime.datetime.now()
        timezone = datetime.datetime.now(datetime.timezone.utc).astimezone().tzname()

        return {
            "timezone": timezone or "UTC",
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "datetime": now.isoformat(),
        }

    def get_environment_info(self) -> Dict[str, str]:
        """获取环境信息

        Returns:
            Dict[str, str]: 环境信息字典，包含 os、python_version、platform
        """
        return {
            "os": platform.system(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "platform": platform.platform(),
        }

    def get_all_model_entries(self) -> List[Dict[str, Any]]:
        """获取所有模型条目（用户配置 + 项目配置合并）

        Returns:
            List[Dict[str, Any]]: 模型条目列表，每个条目包含 source 字段标识来源
        """
        user_config_path, project_config_path, _ = find_config_files()
        
        user_entries = []
        project_entries = []
        
        # 加载用户配置
        if user_config_path:
            try:
                user_config_data = load_config_from_file(user_config_path)
                user_model_section = user_config_data.get("model", {})
                user_entries = user_model_section.get("entries", [])
                if not isinstance(user_entries, list):
                    user_entries = []
            except Exception as e:
                logger.warning(f"加载用户配置模型条目失败: {e}")
        
        # 加载项目配置
        if project_config_path:
            try:
                project_config_data = load_config_from_file(project_config_path)
                project_model_section = project_config_data.get("model", {})
                project_entries = project_model_section.get("entries", [])
                if not isinstance(project_entries, list):
                    project_entries = []
            except Exception as e:
                logger.warning(f"加载项目配置模型条目失败: {e}")
        
        # 合并条目，项目配置优先
        merged_entries = _merge_entries_by_key(user_entries, project_entries, "model")
        
        # 为每个条目添加 source 标识
        project_model_names = {entry.get("model") for entry in project_entries if entry.get("model")}
        
        result = []
        for entry in merged_entries:
            entry_copy = entry.copy()
            model_name = entry_copy.get("model")
            if model_name in project_model_names:
                entry_copy["_source"] = "project"
            else:
                entry_copy["_source"] = "user"
            result.append(entry_copy)
        
        return result

    def get_model_entry_source(self, entry: Dict[str, Any]) -> str:
        """判断模型条目的来源

        Args:
            entry: 模型条目字典

        Returns:
            str: "user" 或 "project"
        """
        return entry.get("_source", "user")

    def update_project_model_default(self, model_name: str) -> None:
        """更新项目配置中的 model.default

        Args:
            model_name: 要设置为默认的模型名称

        Raises:
            ValueError: 如果项目配置文件不存在或无法更新
        """
        _, project_config_path, workspace_dir = find_config_files()
        
        if not project_config_path:
            # 如果项目配置文件不存在，创建它
            project_config_dir = workspace_dir / EFLYCODE_DIR
            project_config_dir.mkdir(parents=True, exist_ok=True)
            project_config_path = project_config_dir / CONFIG_FILE
            
            # 创建初始配置
            config_data = {
                "model": {
                    "default": model_name,
                    "entries": []
                }
            }
        else:
            # 加载现有配置
            try:
                config_data = load_config_from_file(project_config_path)
            except Exception as e:
                logger.error(f"加载项目配置文件失败: {e}")
                raise ValueError(f"无法加载项目配置文件: {e}")
        
        # 更新 model.default
        if "model" not in config_data:
            config_data["model"] = {}
        config_data["model"]["default"] = model_name
        
        # 保存配置
        try:
            with open(project_config_path, "w", encoding="utf-8") as f:
                yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            logger.info(f"已更新项目配置 model.default: {model_name}")
        except Exception as e:
            logger.error(f"保存项目配置文件失败: {e}")
            raise ValueError(f"无法保存项目配置文件: {e}")
        
        # 重新加载配置
        self.config = None
        self._initialized = False

