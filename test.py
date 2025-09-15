from dotenv import load_dotenv

from echo.agent.developer import Developer
from echo.config import GlobalConfig
from echo.ui.console import ConsoleUI
from main import create_llm_engine

# load_dotenv()
#
# llm_engine = create_llm_engine()
# developer = Developer(ui=ConsoleUI(), llm_engine=llm_engine)
# print(developer.system_prompt)
# # developer.interactive_chat()

global_config = GlobalConfig.get_instance()