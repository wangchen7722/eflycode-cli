"""HookPlanner 测试"""

import unittest
from eflycode.core.hooks.planner import HookPlanner, ExecutionPlan
from eflycode.core.hooks.types import CommandHook, HookGroup


class TestHookPlanner(unittest.TestCase):
    """HookPlanner 测试"""

    def setUp(self):
        """设置测试环境"""
        self.planner = HookPlanner()

    def test_plan_execution_parallel(self):
        """测试并行执行计划"""
        hook1 = CommandHook(name="hook1", command="echo 1")
        hook2 = CommandHook(name="hook2", command="echo 2")
        group = HookGroup(sequential=False, hooks=[hook1, hook2])
        plan = self.planner.plan_execution([group])
        self.assertEqual(len(plan.groups), 1)
        hooks, sequential = plan.groups[0]
        self.assertFalse(sequential)
        self.assertEqual(len(hooks), 2)

    def test_plan_execution_sequential(self):
        """测试串行执行计划"""
        hook1 = CommandHook(name="hook1", command="echo 1")
        hook2 = CommandHook(name="hook2", command="echo 2")
        group = HookGroup(sequential=True, hooks=[hook1, hook2])
        plan = self.planner.plan_execution([group])
        # 串行执行时，每个 hook 单独成组
        self.assertEqual(len(plan.groups), 2)
        for hooks, sequential in plan.groups:
            self.assertTrue(sequential)
            self.assertEqual(len(hooks), 1)

    def test_plan_execution_mixed(self):
        """测试混合执行计划"""
        # 并行组
        hook1 = CommandHook(name="hook1", command="echo 1")
        hook2 = CommandHook(name="hook2", command="echo 2")
        parallel_group = HookGroup(sequential=False, hooks=[hook1, hook2])

        # 串行组
        hook3 = CommandHook(name="hook3", command="echo 3")
        sequential_group = HookGroup(sequential=True, hooks=[hook3])

        plan = self.planner.plan_execution([parallel_group, sequential_group])
        # 并行组：1 个组，串行组：1 个组（1 个 hook）
        self.assertEqual(len(plan.groups), 2)
        # 第一个是并行组
        hooks, sequential = plan.groups[0]
        self.assertFalse(sequential)
        # 第二个是串行组
        hooks, sequential = plan.groups[1]
        self.assertTrue(sequential)


class TestExecutionPlan(unittest.TestCase):
    """ExecutionPlan 测试"""

    def test_add_group(self):
        """测试添加执行组"""
        plan = ExecutionPlan()
        hook = CommandHook(name="test", command="echo test")
        plan.add_group([hook], sequential=False)
        self.assertEqual(len(plan.groups), 1)

    def test_add_empty_group(self):
        """测试添加空组"""
        plan = ExecutionPlan()
        plan.add_group([], sequential=False)
        self.assertEqual(len(plan.groups), 0)  # 空组不应该被添加


if __name__ == "__main__":
    unittest.main()

