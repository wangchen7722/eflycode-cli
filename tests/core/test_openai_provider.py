import unittest
from unittest.mock import MagicMock, Mock, patch

from eflycode.core.llm.advisor import Advisor
from eflycode.core.llm.protocol import (
    ChatCompletion,
    ChatCompletionChunk,
    LLMConfig,
    LLMRequest,
    Message,
)
from eflycode.core.llm.providers.base import ProviderCapabilities
from eflycode.core.llm.providers.openai import OpenAiProvider


class TestOpenAiProvider(unittest.TestCase):
    """OpenAiProvider 测试类"""

    def setUp(self):
        """设置测试环境"""
        self.config = LLMConfig(
            api_key="test-api-key",
            base_url="https://api.openai.com/v1",
            timeout=60.0,
            max_retries=3,
            temperature=0.7,
            max_tokens=1000,
        )

        self.request = LLMRequest(
            model="gpt-4",
            messages=[
                Message(role="user", content="Hello, world!"),
            ],
        )

    def test_init(self):
        """测试初始化"""
        with patch("eflycode.core.llm.providers.openai.OpenAI") as mock_openai:
            provider = OpenAiProvider(self.config)
            self.assertEqual(provider.config, self.config)
            self.assertIsNotNone(provider.advisor_chain)
            mock_openai.assert_called_once_with(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                max_retries=self.config.max_retries,
            )

    def test_init_with_advisors(self):
        """测试带 Advisor 的初始化"""
        advisor1 = Mock(spec=Advisor)
        advisor2 = Mock(spec=Advisor)
        advisors = [advisor1, advisor2]

        with patch("eflycode.core.llm.providers.openai.OpenAI"):
            provider = OpenAiProvider(self.config, advisors=advisors)
            self.assertEqual(len(provider.advisor_chain.advisors), 2)

    def test_capabilities(self):
        """测试 capabilities 属性"""
        with patch("eflycode.core.llm.providers.openai.OpenAI"):
            provider = OpenAiProvider(self.config)
            capabilities = provider.capabilities
            self.assertIsInstance(capabilities, ProviderCapabilities)
            self.assertTrue(capabilities.supports_streaming)
            self.assertTrue(capabilities.supports_tools)

    def test_build_api_kwargs_basic(self):
        """测试构建基本 API 参数"""
        with patch("eflycode.core.llm.providers.openai.OpenAI"):
            provider = OpenAiProvider(self.config)
            kwargs = provider._build_api_kwargs(self.request, stream=False)

            self.assertEqual(kwargs["model"], "gpt-4")
            self.assertFalse(kwargs["stream"])
            self.assertIn("messages", kwargs)
            self.assertEqual(len(kwargs["messages"]), 1)
            self.assertEqual(kwargs["messages"][0]["role"], "user")
            self.assertEqual(kwargs["messages"][0]["content"], "Hello, world!")

    def test_build_api_kwargs_with_config_temperature(self):
        """测试使用配置中的 temperature"""
        with patch("eflycode.core.llm.providers.openai.OpenAI"):
            provider = OpenAiProvider(self.config)
            kwargs = provider._build_api_kwargs(self.request, stream=False)
            self.assertEqual(kwargs["temperature"], 0.7)

    def test_build_api_kwargs_with_request_temperature(self):
        """测试使用请求中的 temperature（优先级高于配置）"""
        with patch("eflycode.core.llm.providers.openai.OpenAI"):
            provider = OpenAiProvider(LLMConfig(api_key="test"))
            self.request.generate_config = {"temperature": 0.9}

            kwargs = provider._build_api_kwargs(self.request, stream=False)
            self.assertEqual(kwargs["temperature"], 0.9)

    def test_build_api_kwargs_with_config_max_tokens(self):
        """测试使用配置中的 max_tokens"""
        with patch("eflycode.core.llm.providers.openai.OpenAI"):
            provider = OpenAiProvider(self.config)
            kwargs = provider._build_api_kwargs(self.request, stream=False)
            self.assertEqual(kwargs["max_tokens"], 1000)

    def test_build_api_kwargs_with_request_max_tokens(self):
        """测试使用请求中的 max_tokens（优先级高于配置）"""
        with patch("eflycode.core.llm.providers.openai.OpenAI"):
            provider = OpenAiProvider(LLMConfig(api_key="test"))
            self.request.generate_config = {"max_tokens": 2000}

            kwargs = provider._build_api_kwargs(self.request, stream=False)
            self.assertEqual(kwargs["max_tokens"], 2000)

    def test_build_api_kwargs_with_generate_config(self):
        """测试使用 generate_config 中的其他参数"""
        with patch("eflycode.core.llm.providers.openai.OpenAI"):
            provider = OpenAiProvider(self.config)
            self.request.generate_config = {
                "top_p": 0.9,
                "frequency_penalty": 0.5,
                "presence_penalty": 0.3,
            }

            kwargs = provider._build_api_kwargs(self.request, stream=False)
            self.assertEqual(kwargs["top_p"], 0.9)
            self.assertEqual(kwargs["frequency_penalty"], 0.5)
            self.assertEqual(kwargs["presence_penalty"], 0.3)

    def test_build_api_kwargs_stream(self):
        """测试流式调用的参数"""
        with patch("eflycode.core.llm.providers.openai.OpenAI"):
            provider = OpenAiProvider(self.config)
            kwargs = provider._build_api_kwargs(self.request, stream=True)
            self.assertTrue(kwargs["stream"])

    def test_build_api_kwargs_with_tools(self):
        """测试带工具的 API 参数"""
        from eflycode.core.llm.protocol import ToolDefinition, ToolFunction, ToolFunctionParameters

        with patch("eflycode.core.llm.providers.openai.OpenAI"):
            provider = OpenAiProvider(self.config)
            tool = ToolDefinition(
                function=ToolFunction(
                    name="test_tool",
                    description="Test tool",
                    parameters=ToolFunctionParameters(properties={}),
                )
            )
            self.request.tools = [tool]

            kwargs = provider._build_api_kwargs(self.request, stream=False)
            self.assertIn("tools", kwargs)
            self.assertEqual(len(kwargs["tools"]), 1)
            self.assertEqual(kwargs["tools"][0]["function"]["name"], "test_tool")

    @patch("eflycode.core.llm.providers.openai.OpenAI")
    def test_call(self, mock_openai_class):
        """测试 call 方法"""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.id = "chatcmpl-123"
        mock_response.object = "chat.completion"
        mock_response.created = 1234567890
        mock_response.model = "gpt-4"
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    role="assistant",
                    content="Hello!",
                    tool_calls=None,
                ),
                finish_reason="stop",
            )
        ]
        mock_response.usage = MagicMock(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )

        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAiProvider(self.config)
        response = provider.call(self.request)

        self.assertIsInstance(response, ChatCompletion)
        self.assertEqual(response.id, "chatcmpl-123")
        self.assertEqual(response.model, "gpt-4")
        self.assertEqual(response.message.content, "Hello!")
        self.assertIsNotNone(response.usage)
        self.assertEqual(response.usage.total_tokens, 15)

        mock_client.chat.completions.create.assert_called_once()

    @patch("eflycode.core.llm.providers.openai.OpenAI")
    def test_call_with_advisor(self, mock_openai_class):
        """测试 call 方法通过 Advisor 链"""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.id = "chatcmpl-123"
        mock_response.object = "chat.completion"
        mock_response.created = 1234567890
        mock_response.model = "gpt-4"
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    role="assistant",
                    content="Hello!",
                    tool_calls=None,
                ),
                finish_reason="stop",
            )
        ]
        mock_response.usage = None

        mock_client.chat.completions.create.return_value = mock_response

        advisor = Mock(spec=Advisor)
        advisor.before_call = Mock(return_value=self.request)
        advisor.after_call = Mock(side_effect=lambda req, resp: resp)

        provider = OpenAiProvider(self.config, advisors=[advisor])
        response = provider.call(self.request)

        advisor.before_call.assert_called_once()
        advisor.after_call.assert_called_once()
        self.assertIsInstance(response, ChatCompletion)

    @patch("eflycode.core.llm.providers.openai.OpenAI")
    def test_stream(self, mock_openai_class):
        """测试 stream 方法"""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_chunk1 = MagicMock()
        mock_chunk1.id = "chatcmpl-123"
        mock_chunk1.object = "chat.completion.chunk"
        mock_chunk1.created = 1234567890
        mock_chunk1.model = "gpt-4"
        mock_chunk1.choices = [
            MagicMock(
                delta=MagicMock(role="assistant", content="Hello"),
                finish_reason=None,
            )
        ]
        mock_chunk1.usage = None

        mock_chunk2 = MagicMock()
        mock_chunk2.id = "chatcmpl-123"
        mock_chunk2.object = "chat.completion.chunk"
        mock_chunk2.created = 1234567890
        mock_chunk2.model = "gpt-4"
        mock_chunk2.choices = [
            MagicMock(
                delta=MagicMock(role=None, content="!"),
                finish_reason="stop",
            )
        ]
        mock_chunk2.usage = None

        mock_client.chat.completions.create.return_value = [mock_chunk1, mock_chunk2]

        provider = OpenAiProvider(self.config)
        chunks = list(provider.stream(self.request))

        self.assertEqual(len(chunks), 2)
        self.assertTrue(all(isinstance(chunk, ChatCompletionChunk) for chunk in chunks))
        self.assertEqual(chunks[0].delta.content, "Hello")
        self.assertEqual(chunks[1].delta.content, "!")

    @patch("eflycode.core.llm.providers.openai.OpenAI")
    def test_stream_with_advisor(self, mock_openai_class):
        """测试 stream 方法通过 Advisor 链"""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_chunk = MagicMock()
        mock_chunk.id = "chatcmpl-123"
        mock_chunk.object = "chat.completion.chunk"
        mock_chunk.created = 1234567890
        mock_chunk.model = "gpt-4"
        mock_chunk.choices = [
            MagicMock(
                delta=MagicMock(role="assistant", content="Hello"),
                finish_reason="stop",
            )
        ]
        mock_chunk.usage = None

        mock_client.chat.completions.create.return_value = [mock_chunk]

        advisor = Mock(spec=Advisor)
        advisor.before_stream = Mock(return_value=self.request)
        advisor.after_stream = Mock(side_effect=lambda req, chunk: chunk)

        provider = OpenAiProvider(self.config, advisors=[advisor])
        chunks = list(provider.stream(self.request))

        advisor.before_stream.assert_called_once()
        self.assertEqual(advisor.after_stream.call_count, 1)
        self.assertEqual(len(chunks), 1)

    @patch("eflycode.core.llm.providers.openai.OpenAI")
    def test_call_error_handling(self, mock_openai_class):
        """测试 call 方法的错误处理"""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_client.chat.completions.create.side_effect = Exception("API Error")

        advisor = Mock(spec=Advisor)
        advisor.before_call = Mock(return_value=self.request)
        advisor.on_call_error = Mock(side_effect=Exception)

        provider = OpenAiProvider(self.config, advisors=[advisor])

        with self.assertRaises(Exception):
            provider.call(self.request)

        advisor.on_call_error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
