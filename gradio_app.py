import os
from dotenv import load_dotenv
import gradio as gr
from echoai.agents.agent import AgentResponseChunkType
from echoai.agents import Developer
from echoai.llms import LLMConfig, OpenAIEngine

load_dotenv()


class ChatInterface:
    def __init__(self):
        self.messages = []
        self.waiting_for_tool_response = False
        self.current_tool = None
        self.agent = self._initialize_agent()

    def _initialize_agent(self):
        llm_config = LLMConfig(
            model=os.environ["ECHO_MODEL"],
            base_url=os.environ["ECHO_BASE_URL"],
            api_key=os.environ["ECHO_API_KEY"],
            temperature=0.1
        )

        return Developer(
            llm_engine=OpenAIEngine(llm_config),
        )

    def process_message(self, message, history):
        history.append({
            "role": "user",
            "content": message
        })
        yield history
        if self.waiting_for_tool_response:
            yield from self.handle_tool_response(message, history)
        response = self.agent.run(message, stream=True)
        history.append({
            "role": "assistant",
            "content": ""
        })
        for chunk in response:
            if chunk.type == AgentResponseChunkType.TEXT:
                history[-1]["content"] += chunk.content
                yield history
            elif chunk.type == AgentResponseChunkType.TOOL_CALL:
                if chunk.finish_reason == "tool_calls":
                    for tool_call in chunk.tool_calls:
                        self.current_tool = tool_call
                        self.waiting_for_tool_response = True
                        tool_info = f"需要执行工具: {tool_call['function']['name']}\n请输入 'yes' 或 'no' 确认是否执行"
                        history.append({
                            "role": "assistant",
                            "content": tool_info
                        })
                        yield history
                        return
        yield history

    def handle_tool_response(self, approval, history):
        approval = approval.strip().lower()
        tool_name = self.current_tool["function"]["name"]

        if approval in ["no", "n"]:
            tool_result = f"This is system-generated message. User refused to execute the tool: {tool_name}"
        elif approval not in ["yes", "y"]:
            tool_result = f"This is system-generated message. User refused to execute the tool: {tool_name} and say: {approval}"
        else:
            tool_result = self.agent.execute_tool(self.current_tool)
            history.append({
                "role": "assistant",
                "content": f"工具 {tool_name} 执行完成"
            })
            yield history

        response = self.agent.run(tool_result, stream=True)
        history.append({
            "role": "assistant",
            "content": ""
        })

        for chunk in response:
            if chunk.type == AgentResponseChunkType.TEXT:
                if chunk.content:
                    history[-1]["content"] += chunk.content
                    yield history
            elif chunk.type == AgentResponseChunkType.TOOL_CALL:
                if chunk.finish_reason == "tool_calls":
                    for tool_call in chunk.tool_calls:
                        self.current_tool = tool_call
                        self.waiting_for_tool_response = True
                        tool_info = f"需要执行工具: {tool_call['function']['name']}\n参数: {tool_call['function']['arguments']}\n请输入 'yes' 或 'no' 确认是否执行"
                        history.append({
                            "role": "assistant",
                            "content": tool_info
                        })
                        yield history
                        return

        self.waiting_for_tool_response = False
        self.current_tool = None
        yield history


def create_chat_interface():
    chat = ChatInterface()

    with gr.Blocks(title=f"{chat.agent.name} 智能体") as demo:
        gr.Markdown(f"# {chat.agent.name} 智能体")

        chatbot = gr.Chatbot(
            [],
            type="messages",
            elem_id="chatbot",
            height=600,
            show_label=False
        )

        with gr.Row():
            txt = gr.Textbox(
                show_label=False,
                placeholder="请输入您的需求...",
                container=False
            )

        txt.submit(chat.process_message, [txt, chatbot], [chatbot])
        txt.submit(lambda: "", None, [txt])
    return demo


if __name__ == "__main__":
    demo = create_chat_interface()
    demo.queue()
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False)
