from echoai.core.llms.llm_engine import LLMConfig

from echoai.core.llms.openai_engine import OpenAIEngine
from echoai.core.prompt.prompt_loader import PromptLoader
from echoai.server.models.chat import ChatRequest


class ChatService:
    
    def __init__(self, llm_config: LLMConfig):
        self.llm_engine = OpenAIEngine(llm_config)
        
    def developer_chat(self, chat_request: ChatRequest):
        """利用开发者的能力进行聊天

        Args:
            message: 聊天消息
        """
        system_prompt = PromptLoader.get_instance().render_template(
            "developer/system.prompt",
            tools=chat_request.tools,
            system_info=""
        )