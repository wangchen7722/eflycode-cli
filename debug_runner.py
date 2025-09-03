#!/usr/bin/env python3
"""
调试运行入口

提供将已有智能体直接启动交互模式的便捷方法
"""

from typing import Any

from main import interactive_mode, create_llm_engine


def run_agent_interactive(agent: Any) -> None:
    """调试辅助函数
    
    传入已有智能体实例并直接启动交互模式
    
    Args:
        agent: 智能体实例
    
    Returns:
        None
    
    Raises:
        交互过程中产生的异常由内部处理 不向外抛出
    """
    interactive_mode(agent)


if __name__ == "__main__":
    from echo.agents import Developer
    llm_engine = create_llm_engine()
    run_agent_interactive(Developer(llm_engine=llm_engine))