"""Hook 注册表

负责存储和匹配 hooks
"""

from typing import Dict, List, Optional

from eflycode.core.hooks.types import CommandHook, HookEventName, HookGroup


class HookRegistry:
    """Hook 注册表

    存储 hooks 并按事件名和工具名匹配
    """

    def __init__(self):
        """初始化注册表"""
        # 按事件名存储 hooks，每个事件对应一个 HookGroup 列表
        self._hooks: Dict[HookEventName, List[HookGroup]] = {}

    def register_hook(
        self,
        event_name: HookEventName,
        hook: CommandHook,
        group_matcher: Optional[str] = None,
        sequential: bool = False,
    ) -> None:
        """注册一个 hook

        Args:
            event_name: 事件名称
            hook: Hook 定义
            group_matcher: Hook 组的匹配器，如果提供则创建新组
            sequential: 是否串行执行（仅当 group_matcher 提供时有效）
        """
        if event_name not in self._hooks:
            self._hooks[event_name] = []

        # 如果提供了 group_matcher，创建新组
        if group_matcher is not None:
            group = HookGroup(matcher=group_matcher, sequential=sequential, hooks=[hook])
            self._hooks[event_name].append(group)
        else:
            # 如果没有提供 group_matcher，但 hook 有 matcher，根据 hook 的 matcher 分组
            if hook.matcher:
                # 查找是否有相同 matcher 的组
                target_group = None
                for group in self._hooks[event_name]:
                    if group.matcher == hook.matcher:
                        target_group = group
                        break
                
                if target_group is None:
                    # 创建新组
                    target_group = HookGroup(matcher=hook.matcher, sequential=sequential)
                    self._hooks[event_name].append(target_group)
                
                target_group.hooks.append(hook)
            else:
                # hook 没有 matcher，添加到默认组（matcher=None）
                # 查找默认组
                default_group = None
                for group in self._hooks[event_name]:
                    if group.matcher is None:
                        default_group = group
                        break
                
                if default_group is None:
                    # 创建默认组
                    default_group = HookGroup()
                    self._hooks[event_name].append(default_group)
                
                default_group.hooks.append(hook)

    def register_hook_group(
        self, event_name: HookEventName, group: HookGroup
    ) -> None:
        """注册一个 hook 组

        Args:
            event_name: 事件名称
            group: Hook 组
        """
        if event_name not in self._hooks:
            self._hooks[event_name] = []
        self._hooks[event_name].append(group)

    def get_hooks_for_event(
        self, event_name: HookEventName, tool_name: Optional[str] = None
    ) -> List[HookGroup]:
        """获取匹配指定事件和工具名的 hooks

        Args:
            event_name: 事件名称
            tool_name: 工具名称（可选，用于匹配）

        Returns:
            List[HookGroup]: 匹配的 Hook 组列表
        """
        if event_name not in self._hooks:
            return []

        matched_groups = []
        for group in self._hooks[event_name]:
            # 如果没有工具名，直接包含该组
            if tool_name is None:
                matched_groups.append(group)
            else:
                # 如果提供了工具名，需要同时匹配组的 matcher 和组内每个 hook 的 matcher
                if group.matches_tool(tool_name):
                    # 过滤组内的 hooks，只保留匹配的
                    matched_hooks = [
                        hook for hook in group.hooks if hook.matches_tool(tool_name)
                    ]
                    if matched_hooks:
                        # 创建新的组，只包含匹配的 hooks
                        matched_group = HookGroup(
                            matcher=group.matcher,
                            sequential=group.sequential,
                            hooks=matched_hooks,
                        )
                        matched_groups.append(matched_group)

        return matched_groups

    def get_all_hooks_for_event(
        self, event_name: HookEventName
    ) -> List[HookGroup]:
        """获取指定事件的所有 hooks（不进行工具名匹配）

        Args:
            event_name: 事件名称

        Returns:
            List[HookGroup]: Hook 组列表
        """
        return self._hooks.get(event_name, [])

    def clear_hooks(self) -> None:
        """清空所有 hooks（主要用于测试）"""
        self._hooks.clear()

    def has_hooks(self, event_name: HookEventName) -> bool:
        """检查是否有指定事件的 hooks

        Args:
            event_name: 事件名称

        Returns:
            bool: 是否有 hooks
        """
        return event_name in self._hooks and len(self._hooks[event_name]) > 0

