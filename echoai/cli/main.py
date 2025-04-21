import json
import os
import time

from dotenv import load_dotenv

from echoai.cli.agents.developer import Developer
from echoai.cli.ui.console import ConsoleUI
from echoai.core.agents.agent import Agent, AgentResponseChunkType
from echoai.core.llms.llm_engine import LLMConfig
from echoai.core.llms.openai_engine import OpenAIEngine

load_dotenv()

def run_loop(agent: Agent):
    
    ui = ConsoleUI.get_instance()
    enable_stream = True
    user_input = None
    # tool_call_progress: Optional[LoadingUI] = None
    while True:
        if user_input is None:
            user_input = ui.acquire_user_input()
        if user_input.strip() == "exit" or user_input.strip() == "quit":
            break
        agent_response = agent.run(user_input, stream=enable_stream)
        user_input = None
        if enable_stream:
            for chunk in agent_response:
                if chunk.type == AgentResponseChunkType.TEXT:
                    # 文本输出
                    if not chunk.content:
                        continue
                    ui.show_text(chunk.content, end="")
                elif chunk.type == AgentResponseChunkType.TOOL_CALL:
                    if chunk.content:
                        ui.show_text(chunk.content, end="")
                    # 工具调用
                    # if tool_call_progress is None:
                        # tool_call_progress = ui.create_loading(
                        #     "loading " + chunk.content[1:-1] + " ..."
                        # )
                        # tool_call_progress.start()
                    if chunk.finish_reason != "tool_calls":
                        # 说明工具调用正在生成，跳过
                        continue
                    if chunk.tool_calls is None:
                        # 说明工具调用未生成，跳过
                        continue
                    # tool_call_progress.stop()
                    # tool_call_progress = None
                    # 这里有且仅会有一个工具调用
                    user_input = ""
                    for tool_call in chunk.tool_calls:
                        tool_call_name = tool_call["function"]["name"]
                        tool_call_arguments = json.loads(
                            tool_call["function"]["arguments"]
                        )
                        tool_call_arguments_str = "\n".join(
                            [f"{k}={v}" for k, v in tool_call_arguments.items()]
                        )
                        # 换行
                        ui.show_text("", end="")
                        ui.show_panel(
                            [agent.name, tool_call_name],
                            f"Arguments:\n{tool_call_arguments_str}",
                        )
                        tool = agent._tool_map.get(tool_call_name, None)
                        if not agent.auto_approve and tool.is_approval:
                            # 征求用户同意
                            if not tool:
                                user_input = f"This is system-generated message. {tool_call_name} is not found."
                                break
                            tool_display = tool.display(agent.name)
                            ui.show_text(tool_display)
                            user_approval = ui.acquire_user_input("\[yes/no]")
                            if user_approval.strip().lower() in ["no", "n"]:
                                user_input = f"This is system-generated message. User refused to execute the tool: {tool_call_name}"
                                break
                            elif user_approval.strip().lower() not in ["yes", "y"]:
                                user_input = f"This is system-generated message. User refused to execute the tool: {tool_call_name} and say: {user_approval}"
                                break
                        with ui.create_loading(tool_call_name):
                            tool_call_result = agent.execute_tool(tool_call)
                            time.sleep(0.1)  # 等待一段时间，保证控制台能够输出 loading
                        ui.show_panel(
                            [agent.name, tool_call_name], f"Result:\n{tool_call_result}"
                        )
                        user_input += tool_call_result + "\n"
                elif chunk.type == AgentResponseChunkType.DONE:
                    # 流式输出结束
                    ui.show_text("")  # 换行
                else:
                    raise ValueError(
                        f"Unknown agent response chunk type: {chunk.type}"
                    )


def main():
    llm_config = LLMConfig(
        model=os.environ["ECHO_MODEL"],
        base_url=os.environ["ECHO_BASE_URL"],
        api_key=os.environ["ECHO_API_KEY"],
        temperature=0.1
    )

    developer = Developer(
        name="developer",
        llm_engine=OpenAIEngine(llm_config),
    )
    run_loop(developer)


if __name__ == "__main__":
    main()
