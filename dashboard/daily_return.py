# 文件路徑: dashboard/daily_return.py
import pandas as pd
from figure import get_daily_return_traces


def get_daily_return_traces_with_layout(df: pd.DataFrame):
    """
    返回 Daily Return 圖表的 traces，不包含完整的 go.Figure。
    """
    if df is None or df.empty:
        return []

    # 這裡只返回 traces
    return get_daily_return_traces(df)