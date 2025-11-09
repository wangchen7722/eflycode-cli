from eflycode.ui.base_controller import BaseUIController, UIEvent
from eflycode.util.event_bus import EventBus


class AgentUIEvent(UIEvent):
    """Agent UI 事件枚举"""
    ...


class SmartCompleter(Completer):
    """命令、技能、文件路径的智能补全器"""

    def __init__(self):
        self.commands: List[BaseCommand] = get_builtin_commands()
        self.skills: List[str] = []
        self.files: List[str] = []
        self.max_command_length = max((len(cmd.name) for cmd in self.commands), default=0)

    def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        """根据当前输入返回命令补全建议"""
        text = document.text_before_cursor.strip()
        if not text:
            return

        # 限制匹配范围：只保留末尾可能的命令部分
        text = text[-self.max_command_length:]
        slash_index = text.rfind("/")
        if slash_index != -1:
            prefix = text[slash_index + 1:]
            for cmd in self.commands:
                if cmd.name.startswith(prefix):
                    yield Completion(
                        cmd.name,
                        display=cmd.description,
                        start_position=-len(prefix)
                    )



class CLIController(BaseUIController):
    """命令行界面控制器"""

    def __init__(self, event_bus: EventBus):
        super().__init__(event_bus, supported_event_classes=[AgentUIEvent])
        
    def initialize(self):
        """初始化 UI 控制器"""
        ...

    def run(self):
        """运行UI控制器"""
        ...

    def stop(self):
        """停止UI控制器"""
        ...

    def shutdown(self):
        """关闭UI控制器"""
        ...
