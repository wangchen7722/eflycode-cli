"""CLI 命令处理函数"""

from typing import Awaitable, Callable, Optional

from eflycode.cli.components.model_list import ModelListComponent
from eflycode.cli.output import TerminalOutput
from eflycode.core.config.config_manager import ConfigManager
from eflycode.core.config.models import Config
from eflycode.core.event.events import AppConfigLLMChangedEvent
from eflycode.core.event.event_bus import get_global_event_bus
from eflycode.core.utils.logger import logger


def build_model_command_handler(
    output: TerminalOutput,
    config_manager: ConfigManager,
) -> Callable[[str], Awaitable[bool]]:
    """构建 /model 命令处理函数"""

    async def handle_model_command(command: str) -> bool:
        if command.strip() != "/model":
            return False
        try:
            old_config = config_manager.get_config()
            model_list = ModelListComponent()
            selected_model = await model_list.show()

            if selected_model:
                config_manager.update_project_model_default(selected_model)
                # 同步刷新当前配置，便于后续读取最新 model
                new_config = config_manager.load()
                get_global_event_bus().emit_sync(
                    AppConfigLLMChangedEvent(
                        source=old_config.llm_config,
                        target=new_config.llm_config,
                    )
                )
                output.write(f"\n[已更新默认模型: {selected_model}]\n")
                logger.info(f"用户选择模型: {selected_model}")
            else:
                output.write("\n[取消选择]\n")
        except Exception as e:
            output.write(f"\n[错误: {str(e)}]\n")
            logger.error(f"处理 /model 命令失败: {e}", exc_info=True)
        return True

    return handle_model_command
