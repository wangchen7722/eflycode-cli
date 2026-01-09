"""模型列表选择组件

用于显示和选择模型配置
"""

from typing import Any, Dict, List, Optional

from eflycode.cli.components.select import SelectComponent
from eflycode.core.config.config_manager import ConfigManager
from eflycode.core.ui.errors import UserCanceledError
from eflycode.core.utils.logger import logger


def mask_api_key(api_key: Optional[str]) -> str:
    """掩码 API Key，显示前8位和后4位，中间用星号填充

    Args:
        api_key: API Key 字符串

    Returns:
        str: 掩码后的 API Key
    """
    if not api_key:
        return "未设置"
    
    api_key_str = str(api_key)
    if len(api_key_str) <= 12:
        return "*" * len(api_key_str)
    
    return f"{api_key_str[:8]}{'*' * (len(api_key_str) - 12)}{api_key_str[-4:]}"


class ModelListComponent:
    """模型列表选择组件"""

    async def show(self) -> Optional[str]:
        """显示模型列表并返回选中的模型名称

        Returns:
            Optional[str]: 选中的模型名称，如果取消则返回 None

        Raises:
            UserCanceledError: 如果用户取消选择
        """
        config_manager = ConfigManager.get_instance()
        
        # 获取所有模型条目
        entries = config_manager.get_all_model_entries()
        if not entries:
            logger.warning("没有可用的模型配置")
            return None
        
        # 获取当前默认模型
        current_config = config_manager.get_config()
        current_default = current_config.model_name if current_config else None
        
        # 构建选项列表
        options = []
        for entry in entries:
            model_name = entry.get("model", "")
            display_name = entry.get("name", model_name)
            provider = entry.get("provider", "unknown")
            api_key = entry.get("api_key", "")
            source = config_manager.get_model_entry_source(entry)
            
            # 构建标签
            source_label = "项目" if source == "project" else "用户"
            api_key_masked = mask_api_key(api_key)
            
            label = f"{model_name} ({display_name}) [{source_label}] [{api_key_masked}]"
            
            # 如果是当前默认模型，添加标记
            if model_name == current_default:
                label = f"{label} [当前默认]"
            
            options.append({
                "key": model_name,
                "label": label,
                "description": f"Provider: {provider}",
            })
        
        # 使用 SelectComponent 显示
        select_component = SelectComponent()
        try:
            selected_model = await select_component.show(
                title="选择模型",
                options=options,
                default_key=current_default,
                full_screen=False,
            )
            return selected_model
        except UserCanceledError:
            # 用户取消选择
            logger.debug("用户取消模型选择")
            return None
        except Exception as e:
            logger.error(f"模型选择失败: {e}", exc_info=True)
            return None

