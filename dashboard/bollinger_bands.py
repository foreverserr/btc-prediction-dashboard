# 路径: dashboard/bollinger_bands.py

import pandas as pd
from figure.figure_bollinger import get_bollinger_traces 


def get_bollinger_traces_with_layout(df: pd.DataFrame, period: int = 20, stddev: int = 2) -> list:
    """
    【接口层函数】
    转发对 figure.figure_bollinger.get_bollinger_traces 的调用。
    """
    if df is None or df.empty:
        return []

    return get_bollinger_traces(df, period=period, stddev=stddev)