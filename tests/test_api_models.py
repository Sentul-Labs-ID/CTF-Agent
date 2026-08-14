from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel

from backend.config import Settings
from backend.models import (
    context_window,
    model_id_from_spec,
    resolve_model,
    resolve_model_settings,
)


def test_anthropic_api_model_resolves_without_network():
    settings = Settings(_env_file=None, anthropic_api_key="test-anthropic-key")
    model = resolve_model("anthropic/claude-sonnet-4-6", settings)
    assert isinstance(model, AnthropicModel)
    assert model.model_name == "claude-sonnet-4-6"


def test_groq_slash_model_id_is_preserved_without_network():
    settings = Settings(_env_file=None, groq_api_key="test-groq-key")
    spec = "groq/openai/gpt-oss-120b"
    model = resolve_model(spec, settings)
    assert isinstance(model, OpenAIChatModel)
    assert model.model_name == "openai/gpt-oss-120b"
    assert model_id_from_spec(spec) == "openai/gpt-oss-120b"
    assert context_window(spec) == 131_072


def test_groq_output_allowance_stays_below_on_demand_tpm_limit():
    settings = resolve_model_settings("groq/llama-3.3-70b-versatile")
    assert settings["max_tokens"] == 4_096


def test_latest_gemini_models_resolve_without_network():
    settings = Settings(_env_file=None, gemini_api_key="test-gemini-key")
    for model_id in (
        "gemini-3.5-flash-lite",
        "gemini-3.6-flash",
        "gemini-3.1-pro-preview",
    ):
        model = resolve_model(f"google/{model_id}", settings)
        assert isinstance(model, GoogleModel)
        assert model.model_name == model_id
        assert context_window(f"google/{model_id}") == 1_048_576


def test_gemini_tiers_use_matching_thinking_levels():
    expected = {
        "gemini-3.5-flash-lite": "low",
        "gemini-3.6-flash": "medium",
        "gemini-3.1-pro-preview": "high",
    }
    for model_id, level in expected.items():
        settings = resolve_model_settings(f"google/{model_id}")
        assert settings["google_thinking_config"]["thinking_level"] == level


def test_claude_sdk_effort_suffix_is_not_part_of_model_id():
    assert model_id_from_spec("claude-sdk/claude-opus-4-6/max") == "claude-opus-4-6"
