import os
import unittest
from typing import Generator
from unittest.mock import MagicMock, patch

from echo.llms.openai_engine import OpenAIEngine
from echo.llms.llm_engine import LLMConfig
from echo.llms.schema import ChatCompletion, ChatCompletionChunk


class TestOpenAIEngine(unittest.TestCase):
    def setUp(self):
        self.llm_config = LLMConfig(
            model=os.environ["ECHO_MODEL"],
            base_url=os.environ["ECHO_BASE_URL"],
            api_key=os.environ["ECHO_API_KEY"],
            temperature=0.7,
            max_tokens=10
        )
        self.engine = OpenAIEngine(self.llm_config)

    @patch('httpx.Client')
    def test_generate_completion(self, mock_client):
        messages = [{"role": "user", "content": "Hello"}]
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Hello! How can I help you today?"
                }
            }]
        }
        mock_client.return_value.post.return_value = mock_response
        response = self.engine.generate(messages, stream=False)

        self.assertIsInstance(response, ChatCompletion)
        self.assertTrue(hasattr(response, "choices"))
        self.assertTrue(len(response.choices) > 0)
        self.assertTrue(hasattr(response.choices[0], "message"))
        self.assertTrue(hasattr(response.choices[0].message, "content"))

    @patch('httpx.Client')
    def test_generate_stream(self, mock_client):
        messages = [{"role": "user", "content": "Hello"}]
        mock_response = MagicMock()
        mock_response.iter_lines.return_value = [
            'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1694268762,"model":"gpt-3.5-turbo-0613","choices":[{"delta":{"role":"assistant"},"index":0}]}',
            'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1694268762,"model":"gpt-3.5-turbo-0613","choices":[{"delta":{"content":"Hello"},"index":0}]}',
            'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1694268762,"model":"gpt-3.5-turbo-0613","choices":[{"delta":{"content":" there"},"index":0}]}',
            'data: [DONE]'
        ]
        mock_client.return_value.stream.return_value.__enter__.return_value = mock_response
        response = self.engine.generate(messages, stream=True)
        self.assertIsInstance(response, Generator)
        for chunk in response:
            self.assertIsInstance(chunk, ChatCompletionChunk)
            self.assertTrue(hasattr(chunk, "choices"))
            self.assertTrue(len(chunk.choices) > 0)
            self.assertTrue(hasattr(chunk.choices[0], "delta"))
            self.assertTrue(hasattr(chunk.choices[0].delta, "content"))



if __name__ == "__main__":
    unittest.main()
