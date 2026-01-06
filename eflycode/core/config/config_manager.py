"""配置管理模块

负责查找和加载配置文件，支持从项目目录或用户目录读取配置
"""

import os
from pathlib import Path
from typing import Optional

import yaml

from eflycode.core.llm.protocol import DEFAULT_MAX_CONTEXT_LENGTH, LLMConfig
from eflycode.core.context.strategies import ContextStrategyConfig


class Config:
    """配置类，包含模型配置和工作区信息"""

    def __init__(
        self,
        model_config: LLMConfig,
        model_name: str,
        workspace_dir: Path,
        config_file_path: Optional[Path] = None,
        context_config: Optional[ContextStrategyConfig] = None,
    ):
        """初始化配置

        Args:
            model_config: LLM 配置
            model_name: 模型名称
            workspace_dir: 工作区根目录
            config_file_path: 配置文件路径（如果是从文件加载的）
            context_config: 上下文管理配置
        """
        self.model_config = model_config
        self.model_name = model_name
        self.workspace_dir = workspace_dir
        self.config_file_path = config_file_path
        self.context_config = context_config
        self.context_config = context_config


def find_config_file() -> tuple[Optional[Path], Optional[Path]]:
    """查找配置文件

    查找逻辑：
    1. 从当前目录开始，向上查找最多 2 级目录
    2. 查找 `.eflycode/config.yaml` 文件
    3. 如果找到，返回配置文件路径和根目录（.eflycode 的父目录）
    4. 如果向上 2 级都没找到，从用户主目录的 `.eflycode/config.yaml` 读取
    5. 如果用户目录也没有，返回 None

    Returns:
        tuple[Optional[Path], Optional[Path]]: (配置文件路径, 工作区根目录)
        如果没找到配置文件，返回 (None, None)
    """
    # 保存初始当前目录，用于用户目录配置时返回
    initial_cwd = Path.cwd().resolve()
    current_dir = initial_cwd

    # 向上查找最多 2 级
    for _ in range(3):  # 当前目录 + 向上 2 级 = 3 个目录
        config_path = current_dir / ".eflycode" / "config.yaml"
        if config_path.exists() and config_path.is_file():
            workspace_dir = current_dir
            return config_path, workspace_dir
        current_dir = current_dir.parent

    # 如果都没找到，尝试用户主目录
    user_home = Path.home()
    user_config_path = user_home / ".eflycode" / "config.yaml"
    if user_config_path.exists() and user_config_path.is_file():
        # 用户目录的配置，工作区目录使用初始当前执行目录
        return user_config_path, initial_cwd

    return None, None


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


def load_config() -> Config:
    """加载配置

    查找配置文件并加载，如果找不到则使用默认配置

    Returns:
        Config: 配置对象
    """
    config_path, workspace_dir = find_config_file()
    
    if config_path and workspace_dir:
        # 从文件加载配置
        try:
            config_data = load_config_from_file(config_path)
            model_config = parse_model_config(config_data)
            model_name = get_model_name_from_config(config_data)
            context_config = parse_context_config(config_data)
            
            return Config(
                model_config=model_config,
                model_name=model_name,
                workspace_dir=workspace_dir,
                config_file_path=config_path,
                context_config=context_config,
            )
        except Exception as e:
            # 如果加载失败，使用默认配置
            from eflycode.core.utils.logger import logger
            logger.warning(f"加载配置文件失败: {e}，使用默认配置")
    
    # 使用默认配置
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
    )

