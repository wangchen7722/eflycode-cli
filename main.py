#!/usr/bin/env python3
"""
Echo AI 主程序入口

支持通过命令行参数选择不同的智能体进行交互
"""

import argparse
import os
import sys
from typing import Optional
from dotenv import load_dotenv

from echo.agent.core.agent import Agent
from echo.llm.openai_engine import OpenAIEngine
from echo.llm.llm_engine import LLMConfig
from echo.ui import ConsoleUI

# 加载 .env 文件中的环境变量
load_dotenv()

ui = ConsoleUI()

def create_llm_engine() -> OpenAIEngine:
    """创建LLM引擎实例
    
    从环境变量中读取配置信息创建OpenAI兼容的LLM引擎
    
    Returns:
        OpenAIEngine: 配置好的LLM引擎实例
        
    Raises:
        ValueError: 当必需的环境变量未设置时抛出异常
    """
    # 从环境变量获取配置
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    
    if not api_key:
        raise ValueError("请设置环境变量 OPENAI_API_KEY")
    
    llm_config: LLMConfig = {
        "model": model,
        "base_url": base_url,
        "api_key": api_key,
        "temperature": float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
        "max_tokens": int(os.getenv("OPENAI_MAX_TOKENS", "2048"))
    }
    
    return OpenAIEngine(llm_config)


def create_agent(agent_type: str, llm_engine: OpenAIEngine) -> Optional[object]:
    """根据类型创建智能体实例
    
    Args:
        agent_type: 智能体类型 目前支持 developer
        llm_engine: LLM引擎实例
        
    Returns:
        智能体实例 如果类型不支持则返回None
    """
    if agent_type == "developer":
        from echo.agent.developer import Developer
        return Developer(llm_engine=llm_engine)
    else:
        return None


def interactive_mode(agent: Agent) -> None:
    """交互模式
    
    在此模式下 用户可以持续与智能体进行对话
    
    Args:
        agent: 智能体实例
        
    Raises:
        任意在处理过程中出现的异常会被内部捕获并展示
    """
    ui.welcome()
    while True:
        try:
            # 获取用户输入
            user_input = ui.acquire_user_input()
            
            # 处理特殊命令
            if not user_input.strip():
                continue
            if user_input.lower() in ["quit", "exit"]:
                ui.exit()
            if user_input.lower() == "help":
                ui.help()
                continue
            
            # 调用智能体处理用户输入
            ui.info("\n[bold blue]智能体正在思考...[/bold blue]")
            
            try:
                # 使用流式响应
                response_stream = agent.stream(user_input)
                
                ui.info("\n[bold green]智能体回复:[/bold green]")
                full_response = ""
                
                for chunk in response_stream:
                    if chunk.content:
                        ui.info(chunk.content, end="")
                        ui.flush()
                        full_response += chunk.content
                    
                    # 显示工具调用信息
                    if chunk.tool_calls:
                        for tool_call in chunk.tool_calls:
                            ui.info(f"\n[yellow]执行工具: {tool_call['function']['name']}[/yellow]")
                            if tool_call["function"]["arguments"]:
                                ui.info(f"[dim]参数: {tool_call['function']['arguments']}[/dim]")
                
                ui.info("\n")
                ui.flush()
            except Exception as e:
                ui.error(f"智能体处理请求时发生错误: {str(e)}")
        except KeyboardInterrupt:
            ui.info("\n用户中断操作")
            ui.exit()
        except Exception as e:
            ui.error(f"发生未预期的错误: {str(e)}")


def single_query_mode(agent, query: str) -> None:
    """单次查询模式
    
    执行单次查询后退出程序
    
    Args:
        agent: 智能体实例
        query: 查询内容
        
    Raises:
        任意在处理过程中出现的异常会被内部捕获并展示
    """
    ui.info(f"使用 {agent._name} 智能体处理查询: {query}")
    
    try:
        # 使用非流式响应获取完整结果
        response = agent.run(query, stream=False)
        
        ui.panel(["智能体回复"], response.content)
        ui.flush()
        
        # 显示工具调用信息
        if response.tool_calls:
            ui.info("\n[yellow]执行的工具:[/yellow]")
            for tool_call in response.tool_calls:
                ui.info(f"- {tool_call.function.name}: {tool_call.function.arguments}")
    except Exception as e:
        ui.error(f"处理查询时发生错误: {str(e)}")
        sys.exit(1)


def main() -> None:
    """主函数
    
    解析命令行参数 初始化引擎和智能体 并根据模式运行
    
    Raises:
        ValueError: 当配置缺失或不合法时可能抛出
    """
    parser = argparse.ArgumentParser(
        description="Echo AI - 智能代理系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
1. 启动开发者智能体 交互模式
    python main.py --agent developer

2. 单次查询模式
    python main.py --agent developer --query "帮我创建一个Python项目"
        """
    )
    
    parser.add_argument(
        "--agent",
        type=str,
        default="developer",
        choices=["developer"],
        help="选择智能体类型 默认 developer"
    )
    
    parser.add_argument(
        "--query",
        type=str,
        help="单次查询内容 如果提供则执行单次查询后退出"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        help="配置文件路径 可选"
    )
    
    args = parser.parse_args()

    try:
        ui.welcome()

        llm_engine = create_llm_engine()

        agent = create_agent(args.agent, llm_engine)
        
        if agent is None:
            ui.error(f"不支持的智能体类型: {args.agent}")
            sys.exit(1)
        
        # 根据是否提供查询内容选择运行模式
        if args.query:
            single_query_mode(agent, args.query)
        else:
            interactive_mode(agent)
            
    except ValueError as e:
        ui.error(f"配置错误: {str(e)}")
        ui.info("\n请确保设置了以下环境变量:")
        ui.info("- OPENAI_API_KEY: OpenAI API密钥")
        ui.info("- OPENAI_BASE_URL: API基础URL 可选 默认为官方API")
        ui.info("- OPENAI_MODEL: 模型名称 可选 默认为 gpt-3.5-turbo")
        sys.exit(1)
    except KeyboardInterrupt:
        ui.info("\n程序被用户中断")
        sys.exit(0)
    except Exception as e:
        ui.error(f"程序启动失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()