from llm.llm_factory import get_llm


def test_get_llm_branches(monkeypatch):
    calls = []

    def _fake_init_chat_model(*, model: str, model_provider: str):
        calls.append((model, model_provider))
        return {"model": model, "provider": model_provider}

    monkeypatch.setattr("llm.llm_factory.init_chat_model", _fake_init_chat_model)

    assert get_llm(provider="openai", model="gpt-x")["provider"] == "openai"
    assert get_llm(provider="ollama", model="llama-x")["provider"] == "ollama"
    assert get_llm(provider="local", model="mistral-x")["provider"] == "ollama"

    assert calls == [
        ("gpt-x", "openai"),
        ("llama-x", "ollama"),
        ("mistral-x", "ollama"),
    ]


def test_get_llm_invalid_provider_raises():
    try:
        get_llm(provider="nope")
    except ValueError as e:
        assert "Unsupported provider" in str(e)
    else:
        raise AssertionError("Expected ValueError")

