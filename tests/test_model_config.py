from __future__ import annotations

import json
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.model_config import ModelSettings, create_llm_instance


class OpenAICompatibleProviderTests(unittest.TestCase):
    def test_openai_provider_uses_environment_base_url(self) -> None:
        captured: dict = {}

        class FakeChatOpenAI:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        fake_langchain_openai = types.ModuleType("langchain_openai")
        fake_langchain_openai.ChatOpenAI = FakeChatOpenAI

        with (
            patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY": "test-opencode-key",
                    "OPENAI_BASE_URL": "https://opencode.ai/zen/v1",
                },
            ),
            patch.dict(sys.modules, {"langchain_openai": fake_langchain_openai}),
        ):
            create_llm_instance(
                "deepseek-v4-flash-free",
                ModelSettings(provider="openai"),
            )

        self.assertEqual(captured["openai_api_key"], "test-opencode-key")
        self.assertEqual(captured["base_url"], "https://opencode.ai/zen/v1")

    def test_opencode_models_route_through_openai_provider(self) -> None:
        config_path = Path(__file__).parents[1] / "model_config.json"
        config = json.loads(config_path.read_text())

        self.assertNotIn("opencode", config["categories"])
        self.assertEqual(
            config["models"]["deepseek-v4-flash-free"]["provider"],
            "openai",
        )
        self.assertEqual(
            config["models"]["deepseek-v4-flash"]["provider"],
            "openai",
        )


if __name__ == "__main__":
    unittest.main()
