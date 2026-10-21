# 新文件: figure/figure_kline.py

import plotly.graph_objects as go
import pandas as pd


def get_kline_trace(df: pd.DataFrame) -> list:
    """
    获取纯粹的 K 线图 Candlestick Trace。

    :param df: 包含 K 线数据的 DataFrame (索引应为 open_time)
    :return: 包含 K 线 Trace 的列表
    """
    if df is None or df.empty:
        return []

    # K 线图 Trace
    kline_trace = go.Candlestick(
        x=df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='K线图',
        increasing_line_color='green',
        decreasing_line_color='red'
    )

    return [kline_trace]