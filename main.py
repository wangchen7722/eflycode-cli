from agent.core.response_converter import AgentResponseConverter
from eflycode.config import GlobalConfig
from eflycode.llm.openai_engine import OpenAIEngine
from eflycode.schema.llm import LLMPrompt, Message, ToolDefinition
from tool import FILE_TOOL_GROUP

global_config = GlobalConfig.get_instance()

llm_engine = OpenAIEngine(
    llm_config=global_config.get_default_llm_config(),
    advisors=["buildin_environment_advisor", "buildin_tool_call_advisor"]
)

response = llm_engine.stream(LLMPrompt(
    messages=[Message(
        role="user",
        content="请并行调用插入insert_file和修改edit_file工具, 实现创建test1.py和test2.py两个空文件, 直接执行, 不用询问或告知我，使用任意方法即可"
    )],
    tools=FILE_TOOL_GROUP.list_tool_definitions()
))

convert = AgentResponseConverter()
response = convert.convert_stream(response)
for chunk in response:
    print(chunk)
