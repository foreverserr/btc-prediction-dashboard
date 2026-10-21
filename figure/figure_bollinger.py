# 路径: figure/figure_bollinger.py

import plotly.graph_objects as go
import pandas as pd


def calculate_bollinger_bands(df: pd.DataFrame, window: int = 20, num_std: int = 2) -> pd.DataFrame:
    """
    【纯计算逻辑】
    计算布林带指标，并将结果添加到 DataFrame 中。
    """
    if df is None or df.empty or 'close' not in df.columns:
        return pd.DataFrame()  # 返回空DataFrame

    df['middle_band'] = df['close'].rolling(window=window).mean()
    df['std_dev'] = df['close'].rolling(window=window).std()
    df['upper_band'] = df['middle_band'] + (df['std_dev'] * num_std)
    df['lower_band'] = df['middle_band'] - (df['std_dev'] * num_std)

    # 返回不包含 std_dev 的 DataFrame
    return df.drop(columns=['std_dev'], errors='ignore')


def get_bollinger_traces(df: pd.DataFrame, period: int = 20, stddev: int = 2) -> list:
    """
    【Trace 封装逻辑】
    计算并返回布林带的上轨、中轨和下轨的 Plotly Trace 列表。
    """
    if df is None or df.empty or 'close' not in df.columns or len(df) < period:
        return []

    # 1. 调用集中式计算函数来获取布林带数据
    # 使用 copy() 确保计算不会影响原始 DataFrame
    df_with_bands = calculate_bollinger_bands(df.copy(), window=period, num_std=stddev)

    if df_with_bands is None or df_with_bands.empty:
        return []

    # 2. 创建并返回追踪列表
    traces = []
    group_name = f'bollinger-{period}-{stddev}'

    # 布林带上轨
    traces.append(go.Scatter(
        x=df_with_bands.index,
        y=df_with_bands['upper_band'],
        mode='lines',
        name=f'布林带上轨({period}日)',
        line=dict(color='red', width=1),
        legendgroup=group_name,
        showlegend=True
    ))

    # 布林带中轨 (SMA)
    traces.append(go.Scatter(
        x=df_with_bands.index,
        y=df_with_bands['middle_band'],
        mode='lines',
        name=f'布林带中轨({period}日)',
        line=dict(color='yellow', width=1),
        legendgroup=group_name,
        showlegend=True
    ))

    # 布林带下轨
    traces.append(go.Scatter(
        x=df_with_bands.index,
        y=df_with_bands['lower_band'],
        mode='lines',
        name=f'布林带下轨({period}日)',
        line=dict(color='green', width=1),
        legendgroup=group_name,
        showlegend=True
    ))

    return traces