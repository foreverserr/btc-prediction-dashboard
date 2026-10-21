# 文件路徑: dashboard/macd.py
import pandas as pd
from figure import get_macd_traces

def get_macd_traces_with_layout(df: pd.DataFrame):
    """
    返回 MACD 圖表的 traces，不包含完整的 go.Figure。
    """
    if df is None or df.empty:
        return []

    # 這裡只返回 traces
    return get_macd_traces(df)