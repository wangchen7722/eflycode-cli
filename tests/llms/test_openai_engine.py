import os
import unittest
from typing import Dict, Any, Generator

from echo.llms.openai_engine import OpenAIEngine
from echo.llms.llm_engine import LLMConfig
from echo.llms.schema import ChatCompletion, ChatCompletionChunk


class TestOpenAIEngine(unittest.TestCase):
    def setUp(self):
        self.llm_config = LLMConfig(
            model="deepseek-chat",
            base_url=os.getenv("ECHO_BASE_URL"),
            api_key=os.getenv("ECHO_API_KEY"),
            temperature=0.7,
            max_tokens=10
        )
        self.engine = OpenAIEngine(self.llm_config)

    def test_generate_completion(self):
        messages = [{"role": "user", "content": "Hello"}]
        response = self.engine.generate(messages)

        self.assertIsInstance(response, ChatCompletion)
        self.assertTrue(hasattr(response, "choices"))
        self.assertTrue(len(response.choices) > 0)
        self.assertTrue(hasattr(response.choices[0], "message"))
        self.assertTrue(hasattr(response.choices[0].message, "content"))

    def test_generate_stream(self):
        messages = [{"role": "user", "content": "Hello"}]
        response = self.engine.generate(messages, stream=True)

        self.assertIsInstance(response, Generator)
        chunk = next(response)
        self.assertIsInstance(chunk, ChatCompletionChunk)
        self.assertTrue(hasattr(chunk, "choices"))
        self.assertTrue(len(chunk.choices) > 0)


if __name__ == "__main__":
    unittest.main()
