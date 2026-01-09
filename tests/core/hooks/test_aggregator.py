"""HookAggregator 测试"""

import unittest
from eflycode.core.hooks.aggregator import HookAggregator
from eflycode.core.hooks.types import (
    AggregatedHookResult,
    HookExecutionResult,
    HookOutput,
)


class TestHookAggregator(unittest.TestCase):
    """HookAggregator 测试"""

    def setUp(self):
        """设置测试环境"""
        self.aggregator = HookAggregator()

    def test_aggregate_successful_results(self):
        """测试聚合成功的结果"""
        results = [
            HookExecutionResult(
                hook_name="hook1",
                stdout='{"decision": "allow", "systemMessage": "msg1"}',
                stderr="",
                exit_code=0,
                duration_ms=100,
                success=True,
            ),
            HookExecutionResult(
                hook_name="hook2",
                stdout='{"decision": "deny", "systemMessage": "msg2"}',
                stderr="",
                exit_code=0,
                duration_ms=100,
                success=True,
            ),
        ]
        aggregated = self.aggregator.aggregate_results(results)
        self.assertEqual(aggregated.decision, "deny")  # deny 优先级高于 allow
        self.assertEqual(len(aggregated.system_messages), 2)

    def test_aggregate_blocking_result(self):
        """测试聚合阻断结果"""
        results = [
            HookExecutionResult(
                hook_name="hook1",
                stdout="",
                stderr="Blocked!",
                exit_code=2,  # 阻断错误
                duration_ms=100,
                success=False,
            ),
        ]
        aggregated = self.aggregator.aggregate_results(results)
        self.assertFalse(aggregated.continue_)
        self.assertIn("Blocked!", aggregated.system_messages)

    def test_aggregate_warning_result(self):
        """测试聚合警告结果"""
        results = [
            HookExecutionResult(
                hook_name="hook1",
                stdout="",
                stderr="Warning",
                exit_code=1,  # 警告
                duration_ms=100,
                success=False,
            ),
        ]
        aggregated = self.aggregator.aggregate_results(results)
        # 警告不应该影响 continue
        self.assertTrue(aggregated.continue_)

    def test_aggregate_with_hook_specific_output(self):
        """测试聚合包含特定输出的结果"""
        results = [
            HookExecutionResult(
                hook_name="hook1",
                stdout='{"hookSpecificOutput": {"key": "value1"}}',
                stderr="",
                exit_code=0,
                duration_ms=100,
                success=True,
            ),
            HookExecutionResult(
                hook_name="hook2",
                stdout='{"hookSpecificOutput": {"key": "value2"}}',
                stderr="",
                exit_code=0,
                duration_ms=100,
                success=True,
            ),
        ]
        aggregated = self.aggregator.aggregate_results(results)
        # 后面的覆盖前面的
        self.assertEqual(aggregated.hook_specific_output["key"], "value2")

    def test_merge_results(self):
        """测试合并多个聚合结果"""
        result1 = AggregatedHookResult(decision="allow", continue_=True)
        result2 = AggregatedHookResult(decision="block", continue_=False)
        merged = self.aggregator.merge_results([result1, result2])
        self.assertEqual(merged.decision, "block")
        self.assertFalse(merged.continue_)

    def test_aggregate_empty_results(self):
        """测试聚合空结果"""
        aggregated = self.aggregator.aggregate_results([])
        self.assertIsNone(aggregated.decision)
        self.assertTrue(aggregated.continue_)
        self.assertEqual(len(aggregated.system_messages), 0)

    def test_aggregate_with_continue_false(self):
        """测试聚合包含 continue=false 的结果"""
        results = [
            HookExecutionResult(
                hook_name="hook1",
                stdout='{"continue": false, "systemMessage": "Stop"}',
                stderr="",
                exit_code=0,
                duration_ms=100,
                success=True,
            ),
        ]
        aggregated = self.aggregator.aggregate_results(results)
        self.assertFalse(aggregated.continue_)
        self.assertIn("Stop", aggregated.system_messages)


if __name__ == "__main__":
    unittest.main()

