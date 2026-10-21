# figure/figure_macd.py
import plotly.graph_objects as go
import pandas as pd


def calculate_macd(df: pd.DataFrame, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
    """
    计算 MACD 指标。
    """
    # 步骤 1: 强制将输入数据转换为 DataFrame，并确保包含 'close' 列。
    if isinstance(df, pd.Series):
        if df.name != 'close':
            raise ValueError("Series 必须以 'close' 为名称。")
        df = df.to_frame()

    if 'close' not in df.columns:
        raise ValueError("DataFrame 必须包含 'close' 列。")

    min_data_points = max(fast_period, slow_period, signal_period) + 1
    if len(df) < min_data_points:
        # 如果数据不足，创建一个带有指标列的空DataFrame并返回
        df['MACD'] = None
        df['Signal'] = None
        df['Histogram'] = None
        return df

    # 步骤 2: 执行 MACD 计算
    exp1 = df['close'].ewm(span=fast_period, adjust=False).mean()
    exp2 = df['close'].ewm(span=slow_period, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=signal_period, adjust=False).mean()
    histogram = macd - signal

    # 步骤 3: 将结果添加到 DataFrame
    df['MACD'] = macd
    df['Signal'] = signal
    df['Histogram'] = histogram

    return df

def get_macd_traces(df: pd.DataFrame) -> list:
    """
    获取 MACD 图表的所有 traces。
    """
    if df is None or df.empty:
        return []

    df_with_macd = calculate_macd(df)
    if 'MACD' not in df_with_macd.columns:
        return []

    traces = []
    # MACD 柱状图
    traces.append(go.Bar(
        x=df_with_macd.index,
        y=df_with_macd['Histogram'],
        name='MACD柱状图',
        marker_color=['green' if val >= 0 else 'red' for val in df_with_macd['Histogram']]
    ))
    # MACD 线
    traces.append(go.Scatter(
        x=df_with_macd.index,
        y=df_with_macd['MACD'],
        mode='lines',
        name='MACD线',
        line=dict(color='yellow', width=2)
    ))
    # 信号线
    traces.append(go.Scatter(
        x=df_with_macd.index,
        y=df_with_macd['Signal'],
        mode='lines',
        name='信号线',
        line=dict(color='blue', width=2)
    ))

    return traces