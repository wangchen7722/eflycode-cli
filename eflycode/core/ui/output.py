from abc import ABC, abstractmethod
from typing import Dict


class UIOutput(ABC):
    """UI 输出抽象接口

    定义统一的输出接口，不依赖具体实现
    支持打字机效果、状态更新等操作
    """

    @abstractmethod
    def write(self, text: str) -> None:
        """写入文本

        支持增量写入，用于打字机效果

        Args:
            text: 要写入的文本
        """
        pass


    @abstractmethod
    def clear(self) -> None:
        """清空输出"""
        pass

    @abstractmethod
    def flush(self) -> None:
        """刷新输出缓冲区"""
        pass

    @abstractmethod
    def start_task(self, task_name: str) -> None:
        """开始任务

        Args:
            task_name: 任务名称
        """
        pass

    @abstractmethod
    def end_task(self) -> None:
        """结束任务"""
        pass

    @abstractmethod
    def show_tool_call(self, tool_name: str, arguments: Dict) -> None:
        """显示工具调用

        Args:
            tool_name: 工具名称
            arguments: 工具参数
        """
        pass

    @abstractmethod
    def show_tool_result(self, tool_name: str, result: str) -> None:
        """显示工具执行结果

        Args:
            tool_name: 工具名称
            result: 执行结果
        """
        pass

    @abstractmethod
    def show_error(self, error: Exception) -> None:
        """显示错误信息

        Args:
            error: 错误异常
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """关闭输出

        清理资源
        """
        pass



