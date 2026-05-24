# Visualization agent implementation
from engine.runtime import record_artifact, runtime_from_state
from tools.plotting_tools import plot_bar, save_bar_chart
from utils.debug import debug_state


def visualization_agent(state):
    df = state["result"]
    runtime = runtime_from_state(state)
    debug_state("Visualization Agent Input", state)
    import pandas as pd
    if isinstance(df, pd.DataFrame):
        # If this looks like a schema DataFrame (from describe_table), print it instead of plotting
        schema_cols = set(df.columns.str.lower())
        if {"column_name", "column_type"}.issubset(schema_cols) or "column_name" in schema_cols:
            print("Table schema:")
            print(df)
        elif len(df.columns) >= 2:
            artifact_dir = runtime.artifact_dir
            if artifact_dir:
                artifact = save_bar_chart(df, df.columns[0], df.columns[1], artifact_dir)
                record_artifact(state, artifact)
            else:
                plot_bar(df, df.columns[0], df.columns[1])
    elif isinstance(df, (list, tuple)):
        # Print or display the list of tables or tuples
        print("Tables available:")
        for row in df:
            print(row[0] if isinstance(row, (list, tuple)) else row)
    debug_state("Visualization Agent Output", state)
    return state

