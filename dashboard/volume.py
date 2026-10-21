# 文件路徑: dashboard/volume.py
import pandas as pd

# 從 figure 資料夾匯入繪圖邏輯
from figure.figure_volume import get_volume_traces

# 這個函數將直接返回 Plotly traces
def get_volume_traces_with_layout(df):
    """
    這個函數將直接返回 Plotly traces，而不是完整的 figure 物件。
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []

    # 調用原來的函數來獲取 traces
    return get_volume_traces(df)