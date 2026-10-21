# 文件路徑: dashborad/ma.py
import pandas as pd
from figure import get_price_and_ma_traces

def get_ma_traces(df: pd.DataFrame):
    """
    返回 MA 圖表的 traces，不包含完整的 go.Figure。
    """
    if df is None or df.empty:
        return []

    # 這裡只返回 traces
    return get_price_and_ma_traces(df)