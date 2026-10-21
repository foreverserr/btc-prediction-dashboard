# 路径: figure/figure_rsi.py

import pandas as pd
import plotly.graph_objects as go
import numpy as np


def calculate_rsi(df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    """
    计算指定周期内的 RSI (Relative Index Strength)，并将结果添加到 DataFrame 中。
    （纯计算逻辑，保持不变）
    """
    if 'close' not in df.columns:
        print("DataFrame 缺少 'close' 列，无法计算 RSI。")
        df['RSI'] = None
        return df

    # 确保输入是 DataFrame
    if not isinstance(df, pd.DataFrame):
        print("calculate_rsi 接收到非 DataFrame 类型数据。")
        return pd.DataFrame(columns=df.columns)

    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()

    rs = gain / loss
    rs.replace([np.inf, -np.inf], np.nan, inplace=True)
    rsi = 100 - (100 / (1 + rs))

    df['RSI'] = rsi
    return df


def get_rsi_traces(df: pd.DataFrame, window: int = 14) -> list:
    """
    计算并返回指定周期 RSI 的 Plotly Trace 列表。
    """
    # 调用计算逻辑
    df_with_rsi = calculate_rsi(df.copy(), window=window)

    if 'RSI' not in df_with_rsi.columns or df_with_rsi['RSI'].isnull().all():
        return []

    # 封装成 Trace 对象
    return [
        go.Scatter(
            x=df_with_rsi.index,
            y=df_with_rsi['RSI'],
            mode='lines',
            name=f'RSI ({window}日)',
            line=dict(width=2),
            legendgroup=f'rsi-{window}',
            showlegend=True
        )
    ]