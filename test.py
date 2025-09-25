from echo import llm
from echo.config import GlobalConfig
from echo.llm.openai_engine import OpenAIEngine
from echo.schema.llm import LLMPrompt, Message
from echo.tool.file.file_tool import FILE_TOOL_GROUP

# load_dotenv()
#
# llm_engine = create_llm_engine()
# developer = Developer(ui=ConsoleUI(), llm_engine=llm_engine)
# print(developer.system_prompt)
# # developer.interactive_chat()

# global_config = GlobalConfig.get_instance()
global_config = GlobalConfig.get_instance()

llm_engine = OpenAIEngine(
    llm_config=global_config.get_default_llm_config(), 
    advisors=["buildin_environment_advisor"]
)
print(
    llm_engine.call(
        LLMPrompt(
            messages=[Message(role="user", content="你好, 使用工具帮我创建一个文件sort.py，编写快速排序")],
            tools=FILE_TOOL_GROUP.list_tools()
        )
    )
)
