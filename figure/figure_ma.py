# figure/figure_ma.py
import pandas as pd
import plotly.graph_objects as go


def get_price_and_ma_traces(df: pd.DataFrame, ma_window: list = [5, 10, 20]) -> list:
    """
    获取 K 线图和多个移动平均线的 traces。
    """
    if df is None or df.empty:
        return []

    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    traces = []

    # 绘制移动平均线
    for w in ma_window:
        ma_col = f'MA_{w}'
        df[ma_col] = df['close'].rolling(window=w).mean()

        traces.append(go.Scatter(
            x=df.index,
            y=df[ma_col],
            mode='lines',
            name=f'MA ({w}日)',
        ))

    return traces