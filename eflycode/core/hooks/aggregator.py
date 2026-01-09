"""Hook 结果聚合器

聚合多个 hook 的执行结果
"""

from typing import List

from eflycode.core.hooks.types import (
    AggregatedHookResult,
    HookExecutionResult,
    HookOutput,
)
from eflycode.core.utils.logger import logger


class HookAggregator:
    """Hook 结果聚合器"""

    def aggregate_results(
        self, execution_results: List[HookExecutionResult]
    ) -> AggregatedHookResult:
        """聚合多个 hook 的执行结果

        Args:
            execution_results: 执行结果列表

        Returns:
            AggregatedHookResult: 聚合后的结果
        """
        results_count = len(execution_results)
        logger.debug(f"聚合 hook 结果: count={results_count}")
        aggregated = AggregatedHookResult()
        aggregated.execution_results = execution_results

        # 处理阻断错误
        blocking_results = [r for r in execution_results if r.is_blocking]
        if blocking_results:
            blocking_hook_names = [r.hook_name for r in blocking_results]
            blocking_count = len(blocking_results)
            logger.warning(f"检测到阻断错误: count={blocking_count}, hooks={blocking_hook_names}")
            # 如果有阻断错误，设置 continue 为 False
            aggregated.continue_ = False
            # 使用第一个阻断错误的 stderr 作为系统消息
            if blocking_results[0].stderr:
                aggregated.system_messages.append(blocking_results[0].stderr)

        # 处理成功的 hooks
        successful_results = [r for r in execution_results if r.success]
        for result in successful_results:
            if result.stdout:
                try:
                    hook_output = HookOutput.from_json(result.stdout)
                    aggregated.merge(
                        AggregatedHookResult(
                            decision=hook_output.decision,
                            continue_=hook_output.continue_,
                            system_messages=[hook_output.system_message]
                            if hook_output.system_message
                            else [],
                            hook_specific_output=hook_output.hook_specific_output,
                        )
                    )
                except Exception:
                    # 解析失败，将 stdout 作为系统消息
                    if result.stdout.strip():
                        aggregated.system_messages.append(result.stdout)

        # 处理警告
        warning_results = [r for r in execution_results if r.is_warning]
        if warning_results:
            warning_hook_names = [r.hook_name for r in warning_results]
            warning_count = len(warning_results)
            logger.warning(f"检测到警告: count={warning_count}, hooks={warning_hook_names}")
            for result in warning_results:
                if result.stderr:
                    stderr_preview = result.stderr[:200]
                    logger.warning(f"Hook 警告: name={result.hook_name}, stderr={stderr_preview}")

        messages_count = len(aggregated.system_messages)
        logger.debug(f"聚合完成: continue={aggregated.continue_}, decision={aggregated.decision}, messages_count={messages_count}")
        return aggregated

    def merge_results(
        self, results: List[AggregatedHookResult]
    ) -> AggregatedHookResult:
        """合并多个聚合结果

        Args:
            results: 聚合结果列表

        Returns:
            AggregatedHookResult: 合并后的结果
        """
        if not results:
            return AggregatedHookResult()

        results_count = len(results)
        logger.debug(f"合并聚合结果: count={results_count}")
        merged = results[0]
        for result in results[1:]:
            merged.merge(result)

        logger.debug(f"合并完成: continue={merged.continue_}, decision={merged.decision}")
        return merged

