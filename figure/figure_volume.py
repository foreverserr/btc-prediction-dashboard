# figure/figure_volume.py
import plotly.graph_objects as go
import pandas as pd


def get_volume_traces(df: pd.DataFrame) -> list:
    """
    获取成交量柱状图的 traces。

    这个函数只返回成交量柱状图，不包含任何移动平均线。
    :param df: 包含 K 线数据的 DataFrame
    :return: 包含成交量柱状图 trace 的列表
    """
    if df is None or df.empty:
        return []

    traces = []

    # 根据价格涨跌设置成交量柱状图颜色
    colors = ['green' if close >= open_ else 'red' for open_, close in zip(df['open'], df['close'])]

    # 添加成交量柱状图
    traces.append(go.Bar(
        x=df.index,
        y=df['volume'],
        name='成交量',
        marker_color=colors,
    ))

    return traces