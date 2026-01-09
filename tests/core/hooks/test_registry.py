"""HookRegistry 测试"""

import unittest
from eflycode.core.hooks.registry import HookRegistry
from eflycode.core.hooks.types import CommandHook, HookEventName, HookGroup


class TestHookRegistry(unittest.TestCase):
    """HookRegistry 测试"""

    def setUp(self):
        """设置测试环境"""
        self.registry = HookRegistry()

    def test_register_hook(self):
        """测试注册 hook"""
        hook = CommandHook(name="test", command="echo test")
        self.registry.register_hook(HookEventName.BEFORE_TOOL, hook)
        self.assertTrue(self.registry.has_hooks(HookEventName.BEFORE_TOOL))

    def test_get_hooks_for_event(self):
        """测试获取事件的 hooks"""
        hook = CommandHook(name="test", command="echo test")
        self.registry.register_hook(HookEventName.BEFORE_TOOL, hook)
        groups = self.registry.get_hooks_for_event(HookEventName.BEFORE_TOOL)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0].hooks), 1)

    def test_get_hooks_with_tool_name(self):
        """测试根据工具名获取 hooks"""
        hook1 = CommandHook(name="hook1", command="echo 1", matcher="write_file")
        hook2 = CommandHook(name="hook2", command="echo 2", matcher="read_file")
        self.registry.register_hook(HookEventName.BEFORE_TOOL, hook1)
        self.registry.register_hook(HookEventName.BEFORE_TOOL, hook2)

        # 匹配 write_file
        groups = self.registry.get_hooks_for_event(
            HookEventName.BEFORE_TOOL, tool_name="write_file"
        )
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].hooks[0].name, "hook1")

        # 匹配 read_file
        groups = self.registry.get_hooks_for_event(
            HookEventName.BEFORE_TOOL, tool_name="read_file"
        )
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].hooks[0].name, "hook2")

    def test_register_hook_with_group(self):
        """测试注册带组的 hook"""
        hook = CommandHook(name="test", command="echo test")
        self.registry.register_hook(
            HookEventName.BEFORE_TOOL, hook, group_matcher="write_file", sequential=True
        )
        groups = self.registry.get_hooks_for_event(HookEventName.BEFORE_TOOL)
        self.assertEqual(len(groups), 1)
        self.assertTrue(groups[0].sequential)
        self.assertEqual(groups[0].matcher, "write_file")

    def test_register_hook_group(self):
        """测试注册 hook 组"""
        hook1 = CommandHook(name="hook1", command="echo 1")
        hook2 = CommandHook(name="hook2", command="echo 2")
        group = HookGroup(matcher="write_file", sequential=True, hooks=[hook1, hook2])
        self.registry.register_hook_group(HookEventName.BEFORE_TOOL, group)
        groups = self.registry.get_hooks_for_event(HookEventName.BEFORE_TOOL)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0].hooks), 2)

    def test_clear_hooks(self):
        """测试清空 hooks"""
        hook = CommandHook(name="test", command="echo test")
        self.registry.register_hook(HookEventName.BEFORE_TOOL, hook)
        self.assertTrue(self.registry.has_hooks(HookEventName.BEFORE_TOOL))
        self.registry.clear_hooks()
        self.assertFalse(self.registry.has_hooks(HookEventName.BEFORE_TOOL))

    def test_get_all_hooks_for_event(self):
        """测试获取事件的所有 hooks"""
        hook1 = CommandHook(name="hook1", command="echo 1", matcher="write_file")
        hook2 = CommandHook(name="hook2", command="echo 2", matcher="read_file")
        self.registry.register_hook(HookEventName.BEFORE_TOOL, hook1)
        self.registry.register_hook(HookEventName.BEFORE_TOOL, hook2)
        groups = self.registry.get_all_hooks_for_event(HookEventName.BEFORE_TOOL)
        self.assertEqual(len(groups), 2)


if __name__ == "__main__":
    unittest.main()

