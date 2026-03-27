# Pandas tools implementation
import pandas as pd


def summarize_df(df: pd.DataFrame):
    return df.describe()