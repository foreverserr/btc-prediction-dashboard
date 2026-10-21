# 新文件: dashboard/kline_chart.py

import pandas as pd
# 从 figure 文件夹导入 K 线绘图逻辑
from figure.figure_kline import get_kline_trace


def get_pure_kline_trace(df: pd.DataFrame) -> list:
    """
    获取纯 K 线图的 Plotly traces。

    :param df: 包含 K 线数据的 DataFrame
    :return: 包含 K 线 trace 的列表
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []

    # 调用 figure 文件中的函数来获取 K 线 trace
    return get_kline_trace(df)