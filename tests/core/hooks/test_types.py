"""Hooks 类型定义测试"""

import unittest
from eflycode.core.hooks.types import (
    CommandHook,
    HookEventName,
    HookGroup,
    HookOutput,
    HookExecutionResult,
    AggregatedHookResult,
)


class TestHookEventName(unittest.TestCase):
    """HookEventName 枚举测试"""

    def test_all_events_exist(self):
        """测试所有事件类型都存在"""
        events = [
            HookEventName.SESSION_START,
            HookEventName.SESSION_END,
            HookEventName.BEFORE_AGENT,
            HookEventName.AFTER_AGENT,
            HookEventName.BEFORE_MODEL,
            HookEventName.AFTER_MODEL,
            HookEventName.BEFORE_TOOL_SELECTION,
            HookEventName.BEFORE_TOOL,
            HookEventName.AFTER_TOOL,
            HookEventName.PRE_COMPRESS,
            HookEventName.NOTIFICATION,
        ]
        self.assertEqual(len(events), 11)


class TestCommandHook(unittest.TestCase):
    """CommandHook 测试"""

    def test_create_hook(self):
        """测试创建 hook"""
        hook = CommandHook(
            name="test_hook",
            command="echo test",
            timeout=5000,
            matcher="write_file",
        )
        self.assertEqual(hook.name, "test_hook")
        self.assertEqual(hook.command, "echo test")
        self.assertEqual(hook.timeout, 5000)
        self.assertEqual(hook.matcher, "write_file")

    def test_default_timeout(self):
        """测试默认超时时间"""
        hook = CommandHook(name="test", command="echo test")
        self.assertEqual(hook.timeout, 60000)

    def test_matches_tool_wildcard(self):
        """测试通配符匹配"""
        hook = CommandHook(name="test", command="echo", matcher="*")
        self.assertTrue(hook.matches_tool("write_file"))
        self.assertTrue(hook.matches_tool("read_file"))

    def test_matches_tool_none_matcher(self):
        """测试无匹配器时匹配所有"""
        hook = CommandHook(name="test", command="echo", matcher=None)
        self.assertTrue(hook.matches_tool("write_file"))

    def test_matches_tool_regex(self):
        """测试正则表达式匹配"""
        hook = CommandHook(name="test", command="echo", matcher="write_.*")
        self.assertTrue(hook.matches_tool("write_file"))
        self.assertFalse(hook.matches_tool("read_file"))

    def test_matches_tool_exact(self):
        """测试精确匹配"""
        hook = CommandHook(name="test", command="echo", matcher="write_file")
        self.assertTrue(hook.matches_tool("write_file"))
        self.assertFalse(hook.matches_tool("read_file"))


class TestHookGroup(unittest.TestCase):
    """HookGroup 测试"""

    def test_create_group(self):
        """测试创建 hook 组"""
        hook1 = CommandHook(name="hook1", command="echo 1")
        hook2 = CommandHook(name="hook2", command="echo 2")
        group = HookGroup(matcher="write_file", sequential=True, hooks=[hook1, hook2])
        self.assertEqual(group.matcher, "write_file")
        self.assertTrue(group.sequential)
        self.assertEqual(len(group.hooks), 2)

    def test_matches_tool(self):
        """测试工具匹配"""
        group = HookGroup(matcher="write_file")
        self.assertTrue(group.matches_tool("write_file"))
        self.assertFalse(group.matches_tool("read_file"))


class TestHookExecutionResult(unittest.TestCase):
    """HookExecutionResult 测试"""

    def test_create_result(self):
        """测试创建执行结果"""
        result = HookExecutionResult(
            hook_name="test",
            stdout="output",
            stderr="error",
            exit_code=0,
            duration_ms=100,
            success=True,
        )
        self.assertEqual(result.hook_name, "test")
        self.assertEqual(result.stdout, "output")
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.success)

    def test_is_blocking(self):
        """测试阻断错误判断"""
        result = HookExecutionResult(
            hook_name="test", stdout="", stderr="", exit_code=2, duration_ms=0, success=False
        )
        self.assertTrue(result.is_blocking)

    def test_is_warning(self):
        """测试警告判断"""
        result = HookExecutionResult(
            hook_name="test", stdout="", stderr="", exit_code=1, duration_ms=0, success=False
        )
        self.assertTrue(result.is_warning)


class TestHookOutput(unittest.TestCase):
    """HookOutput 测试"""

    def test_from_json(self):
        """测试从 JSON 解析"""
        json_str = '{"decision": "allow", "continue": true, "systemMessage": "test"}'
        output = HookOutput.from_json(json_str)
        self.assertEqual(output.decision, "allow")
        self.assertTrue(output.continue_)
        self.assertEqual(output.system_message, "test")

    def test_from_json_with_specific_output(self):
        """测试从 JSON 解析包含特定输出"""
        json_str = '{"hookSpecificOutput": {"key": "value"}}'
        output = HookOutput.from_json(json_str)
        self.assertEqual(output.hook_specific_output, {"key": "value"})

    def test_from_invalid_json(self):
        """测试无效 JSON"""
        output = HookOutput.from_json("invalid json")
        self.assertIsNone(output.decision)
        self.assertTrue(output.continue_)


class TestAggregatedHookResult(unittest.TestCase):
    """AggregatedHookResult 测试"""

    def test_create_result(self):
        """测试创建聚合结果"""
        result = AggregatedHookResult(
            decision="allow",
            continue_=True,
            system_messages=["msg1", "msg2"],
        )
        self.assertEqual(result.decision, "allow")
        self.assertTrue(result.continue_)
        self.assertEqual(len(result.system_messages), 2)

    def test_system_message_property(self):
        """测试系统消息属性"""
        result = AggregatedHookResult(system_messages=["msg1", "msg2"])
        self.assertEqual(result.system_message, "msg1\nmsg2")

    def test_merge_results(self):
        """测试合并结果"""
        result1 = AggregatedHookResult(decision="allow", continue_=True)
        result2 = AggregatedHookResult(decision="block", continue_=False, system_messages=["error"])
        result1.merge(result2)
        self.assertEqual(result1.decision, "block")  # block 优先级更高
        self.assertFalse(result1.continue_)
        self.assertEqual(len(result1.system_messages), 1)


if __name__ == "__main__":
    unittest.main()

