"""CommandRegistry 测试"""

import unittest

from eflycode.cli.command_registry import CommandRegistry, get_command_registry
from eflycode.cli.output import TerminalOutput
from eflycode.core.config.config_manager import ConfigManager


class TestCommandRegistry(unittest.TestCase):
    """CommandRegistry 测试类"""

    def test_register_builtin(self):
        registry = CommandRegistry()
        self.assertIn("/model", registry.list_commands())

    def test_initialize_sets_handler(self):
        registry = CommandRegistry()
        handler = registry.get_command_handler("/model")
        self.assertTrue(callable(handler))

    def test_set_command_handler_not_registered(self):
        registry = CommandRegistry()
        with self.assertRaises(ValueError):
            registry.set_command_handler("/nope", lambda _: True)

    def test_global_registry_singleton(self):
        registry1 = get_command_registry()
        registry2 = get_command_registry()
        self.assertIs(registry1, registry2)


if __name__ == "__main__":
    unittest.main()
