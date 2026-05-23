# LLM factory implementation
from langchain.chat_models import init_chat_model
from typing import Any, Optional

def get_llm(provider: str = "local", model: Optional[str] = None):

    if provider == "openai":
        return init_chat_model(
            model=model or "gpt-4o-mini",
            model_provider="openai"
        )

    elif provider == "ollama":
        return init_chat_model(
            model=model or "llama3",
            model_provider="ollama"
        )

    elif provider == "local":
        return init_chat_model(
            model=model or "mistral",
            model_provider="ollama"
        )

    else:
        raise ValueError("Unsupported provider")


def resolve_llm(state: dict[str, Any]):
    return state.get("llm") or get_llm()
