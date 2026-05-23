from types import SimpleNamespace

from agents.planner_agent import planner_agent


class _StubLLM:
    def invoke(self, _prompt: str):
        return SimpleNamespace(content="Injected plan")


def test_agent_uses_injected_llm():
    state = {"user_query": "question", "llm": _StubLLM()}

    out = planner_agent(state)

    assert out["plan"] == "Injected plan"
