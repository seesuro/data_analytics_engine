# Visualization agent implementation
from tools.plotting_tools import plot_bar


def visualization_agent(state):
    df = state["result"]

    if df is not None and len(df.columns) >= 2:
        plot_bar(df, df.columns[0], df.columns[1])

    return state

