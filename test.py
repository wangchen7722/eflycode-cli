from dotenv import load_dotenv

from echo.agent.developer import Developer
from main import create_llm_engine

load_dotenv()

llm_engine = create_llm_engine()
developer = Developer(llm_engine=llm_engine)

print(developer.system_prompt)
