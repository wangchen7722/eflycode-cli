import os

from dotenv import load_dotenv

from echo.agents import Developer
from echo.llms import LLMConfig
from echo.llms import OpenAIEngine


load_dotenv()

llm_config = LLMConfig(
    model=os.environ["ECHO_MODEL"],
    base_url=os.environ["ECHO_BASE_URL"],
    api_key=os.environ["ECHO_API_KEY"],
    temperature=0.1
)

developer = Developer(
    name="developer",
    llm_engine=OpenAIEngine(llm_config)
)
developer.run_loop()
# print(developer.system_prompt())
