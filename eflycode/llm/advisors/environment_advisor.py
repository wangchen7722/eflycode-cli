from eflycode.llm.advisor import Advisor, register_advisor
from eflycode.schema.llm import LLMRequest, Message
from eflycode.util.system import get_system_environment
from eflycode.prompt.prompt_loader import PromptLoader


@register_advisor("buildin_environment_advisor")
class EnvironmentAdvisor(Advisor):
    """收集当前系统环境信息并拼接到提示词末尾的 Advisor"""
    
    def get_priority(self) -> int:
        """获取 Advisor 的优先级"""
        return -100
    
    def is_builtin_advisor(self) -> bool:
        """判断是否为系统内置 Advisor"""
        return True
    
    def _append_system_info(self, messages: list[Message]) -> list[Message]:
        """将系统环境信息拼接到消息末尾"""
        if not messages:
            return messages
        
        # 获取系统环境信息
        system_environment = get_system_environment()
        
        # 使用 PromptLoader 渲染系统环境模板
        system_environment_text = PromptLoader.get_instance().render_template(
            "environment/system_environment.prompt",
            system_environment=system_environment
        )
        
        # 找到最后一条系统消息，如果没有则创建一条
        last_system_index = -1
        for i, message in enumerate(messages):
            if message.role == "system":
                last_system_index = i
        
        if last_system_index >= 0:
            # 在最后一条系统消息后追加系统信息
            messages[last_system_index].content += "\n\n" + system_environment_text
        else:
            # 如果没有系统消息，在开头插入一条
            system_message = Message(role="system", content=system_environment_text)
            messages.insert(0, system_message)
        
        return messages
    
    def before_call(self, request: LLMRequest) -> LLMRequest:
        """在非流式请求发送前调用，添加系统环境信息"""
        request.messages = self._append_system_info(request.messages)
        return request
    
    def before_stream(self, request: LLMRequest) -> LLMRequest:
        """在流式请求发送前调用，添加系统环境信息"""
        request.messages = self._append_system_info(request.messages)
        return request