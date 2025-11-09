from eflycode.command.base import Command, CommandContext
from eflycode.command.registry import register_command, CommandRegistry


@register_command
class HelpCommand(Command):
    name = "help"
    description = "显示所有可用命令"

    def execute(self, context: CommandContext):
        commands = CommandRegistry.list()
        lines = ["支持的命令："]
        for cmd, desc in commands:
            cmd_name = cmd.name if isinstance(cmd, type) else cmd.__class__.name
            desc = cmd.description if isinstance(cmd, type) else cmd.__class__.description
            lines.append(f"  {cmd_name:<10} - {desc}")
        output = "\n".join(lines)
        context.reply(output)
        return output