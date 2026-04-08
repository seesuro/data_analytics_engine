# Visualization agent implementation
from tools.plotting_tools import plot_bar
from utils.debug import debug_state

def visualization_agent(state):
    df = state["result"]
    debug_state("Visualization Agent Input", state)
    if df is not None and len(df.columns) >= 2:
        plot_bar(df, df.columns[0], df.columns[1])
    debug_state("Visualization Agent Output", state)
    return state

