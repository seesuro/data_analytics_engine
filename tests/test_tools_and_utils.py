from types import SimpleNamespace

import pandas as pd

from tools.pandas_tools import summarize_df
from tools.plotting_tools import plot_bar
from utils.debug import debug_state


def test_summarize_df_returns_description():
    df = pd.DataFrame({"x": [1, 2, 3], "y": [10, 20, 30]})
    desc = summarize_df(df)
    assert "x" in desc.columns
    assert "y" in desc.columns


def test_plot_bar_does_not_require_gui(monkeypatch):
    # Ensure no GUI window pops up during tests.
    monkeypatch.setattr("tools.plotting_tools.plt.show", lambda: None)
    # Avoid calling pandas' plotting backend; we only want to cover our wrapper.
    monkeypatch.setattr(pd.DataFrame, "plot", lambda *args, **kwargs: SimpleNamespace())

    df = pd.DataFrame({"a": ["u", "v"], "b": [1, 2]})
    plot_bar(df, "a", "b")


def test_debug_state_handles_unprintable():
    class _BadStr:
        def __str__(self):
            raise ValueError("nope")

    debug_state("stage", {"ok": 1, "bad": _BadStr()})

