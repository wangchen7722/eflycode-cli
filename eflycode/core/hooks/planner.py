"""Hook 执行计划器

决定 hooks 的执行顺序（并行或串行）
"""

from typing import List

from eflycode.core.hooks.types import CommandHook, HookGroup


class ExecutionPlan:
    """执行计划

    Attributes:
        groups: 执行组列表，每个组包含需要一起执行的 hooks 和执行模式
    """

    def __init__(self):
        """初始化执行计划"""
        self.groups: List[tuple[List[CommandHook], bool]] = []
        # 每个元组是 (hooks, sequential)，sequential 为 True 表示串行执行

    def add_group(self, hooks: List[CommandHook], sequential: bool) -> None:
        """添加一个执行组

        Args:
            hooks: Hook 列表
            sequential: 是否串行执行
        """
        if hooks:
            self.groups.append((hooks, sequential))


class HookPlanner:
    """Hook 执行计划器

    根据 hook 组的配置决定执行顺序
    """

    def plan_execution(self, hook_groups: List[HookGroup]) -> ExecutionPlan:
        """制定执行计划

        Args:
            hook_groups: Hook 组列表

        Returns:
            ExecutionPlan: 执行计划
        """
        plan = ExecutionPlan()

        for group in hook_groups:
            if group.sequential:
                # 串行执行：每个 hook 单独成组
                for hook in group.hooks:
                    plan.add_group([hook], sequential=True)
            else:
                # 并行执行：所有 hooks 一起执行
                plan.add_group(group.hooks, sequential=False)

        return plan

