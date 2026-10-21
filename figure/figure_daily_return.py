# figure/figure_daily_return.py
import plotly.graph_objects as go
import pandas as pd

def calculate_daily_return(df: pd.DataFrame):
    if df is None or df.empty: return df
    df['Daily_Return'] = df['close'].pct_change() * 100
    return df

def get_daily_return_traces(df: pd.DataFrame) -> list:
    """
    获取每日回报率的 traces。
    """
    if df is None or df.empty:
        return []

    df_with_return = calculate_daily_return(df)

    traces = []
    # 分离正回报率和负回报率数据
    positive_returns = df_with_return[df_with_return['Daily_Return'] >= 0]
    negative_returns = df_with_return[df_with_return['Daily_Return'] < 0]

    # 正回报率柱状图
    traces.append(go.Bar(
        x=positive_returns.index,
        y=positive_returns['Daily_Return'],
        name='正回报率',
        marker_color='green'
    ))

    # 负回报率柱状图
    traces.append(go.Bar(
        x=negative_returns.index,
        y=negative_returns['Daily_Return'],
        name='负回报率',
        marker_color='red'
    ))

    return traces