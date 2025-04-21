import os
import unittest
from typing import Generator, List
from unittest.mock import MagicMock, patch

from echoai.core.llms.llm_engine import LLMConfig
from echoai.core.llms.openai_engine import OpenAIEngine
from echoai.core.llms.schema import Message


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

    @patch("httpx.Client.post")
    def test_generate_completion(self, mock_post):
        messages: List[Message] = [{"role": "user", "content": "Hello"}]
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Hello! How can I help you today?"
                }
            }]
        }
        mock_post.return_value = mock_response
        response = self.engine.generate(messages, stream=False)
        print(response)
        print(hasattr(response, "choices"))
        self.assertTrue("choices" in response)
        self.assertTrue(len(response["choices"]) > 0)
        self.assertTrue("message" in response["choices"][0])
        self.assertTrue("content" in response["choices"][0]["message"])

    @patch('httpx.Client.stream')
    def test_generate_stream(self, mock_stream):
        messages: List[Message] = [{"role": "user", "content": "Hello"}]
        mock_response = MagicMock()
        mock_response.iter_lines.return_value = [
            'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1694268762,"model":"gpt-3.5-turbo-0613","choices":[{"delta":{"role":"assistant", "content": ""},"index":0}]}',
            'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1694268762,"model":"gpt-3.5-turbo-0613","choices":[{"delta":{"content":"Hello"},"index":0}]}',
            'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1694268762,"model":"gpt-3.5-turbo-0613","choices":[{"delta":{"content":" there"},"index":0}]}',
            'data: [DONE]'
        ]
        mock_stream.return_value.__enter__.return_value = mock_response
        response = self.engine.generate(messages, stream=True)
        self.assertIsInstance(response, Generator)
        for chunk in response:
            self.assertTrue("choices" in chunk)
            self.assertTrue(len(chunk["choices"]) > 0)
            self.assertTrue("delta" in chunk["choices"][0])
            self.assertTrue("content" in chunk["choices"][0]["delta"])



if __name__ == "__main__":
    unittest.main()
