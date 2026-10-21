# 路径: dashboard/rsi.py

import pandas as pd
from figure import get_rsi_traces


def get_rsi_traces_with_layout(df: pd.DataFrame, window: int = 14) -> list:
    """
    【接口层函数】
    返回指定周期 RSI 的 traces。这个接口函数只负责从 figure 层获取 traces。
    """
    if df is None or df.empty:
        return []

    # 调用 figure/figure_rsi.py 中的 get_rsi_traces
    return get_rsi_traces(df, window=window)
