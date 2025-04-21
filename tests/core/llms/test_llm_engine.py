import unittest

from echoai.core.llms.llm_engine import LLMConfig, LLMEngine, build_generate_config


class TestLLMEngine(unittest.TestCase):
    def setUp(self):
        self.valid_config = LLMConfig(
            model="test-model",
            base_url="http://test.com",
            api_key="test-key",
            temperature=0.7,
            max_tokens=100
        )

    def test_init_with_valid_config(self):
        engine = LLMEngine(self.valid_config)
        self.assertEqual(engine.model, "test-model")
        self.assertEqual(engine.base_url, "http://test.com")
        self.assertEqual(engine.api_key, "test-key")

    def test_init_missing_model(self):
        invalid_config = LLMConfig(
            base_url="http://test.com",
            api_key="test-key"
        )
        with self.assertRaises(ValueError) as context:
            LLMEngine(invalid_config)
        self.assertIn("model", str(context.exception))

    def test_init_missing_base_url(self):
        invalid_config = LLMConfig(
            model="test-model",
            api_key="test-key"
        )
        with self.assertRaises(ValueError) as context:
            LLMEngine(invalid_config)
        self.assertIn("base_url", str(context.exception))

    def test_init_missing_api_key(self):
        invalid_config = LLMConfig(
            model="test-model",
            base_url="http://test.com"
        )
        with self.assertRaises(ValueError) as context:
            LLMEngine(invalid_config)
        self.assertIn("api_key", str(context.exception))

    def test_build_generate_config(self):
        config = build_generate_config(
            self.valid_config,
            stream=True,
            invalid_key="should_not_be_included"
        )
        self.assertEqual(config["temperature"], 0.7)
        self.assertEqual(config["max_tokens"], 100)
        self.assertNotIn("invalid_key", config)

    def test_build_generate_config_override(self):
        config = build_generate_config(
            self.valid_config,
            temperature=0.9,
            max_tokens=200
        )
        self.assertEqual(config["temperature"], 0.9)
        self.assertEqual(config["max_tokens"], 200)

    def test_generate_not_implemented(self):
        engine = LLMEngine(self.valid_config)
        with self.assertRaises(NotImplementedError):
            engine.generate([{"role": "user", "content": "test"}])


if __name__ == "__main__":
    unittest.main()