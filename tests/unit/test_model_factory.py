from __future__ import annotations

import pytest
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from pr_review_agent.models.factory import ModelConfig, build_llm


def test_build_openai() -> None:
    llm = build_llm(ModelConfig(provider="openai", model="gpt-4o-mini", api_key="sk-test"))
    assert isinstance(llm, ChatOpenAI)
    assert llm.model_name == "gpt-4o-mini"


def test_build_openai_with_base_url() -> None:
    cfg = ModelConfig(
        provider="openai",
        model="llama-3",
        api_key="ollama",
        base_url="http://localhost:11434/v1",
    )
    llm = build_llm(cfg)
    assert isinstance(llm, ChatOpenAI)


def test_build_anthropic() -> None:
    llm = build_llm(
        ModelConfig(
            provider="anthropic",
            model="claude-haiku-4",
            api_key="sk-ant-test",
        )
    )
    assert isinstance(llm, ChatAnthropic)


def test_temperature_validation() -> None:
    with pytest.raises(ValueError):
        ModelConfig(provider="openai", model="gpt-4o", temperature=3.0)


def test_max_tokens_must_be_positive() -> None:
    with pytest.raises(ValueError):
        ModelConfig(provider="openai", model="gpt-4o", max_tokens=0)
