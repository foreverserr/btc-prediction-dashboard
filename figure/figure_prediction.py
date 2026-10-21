# figure/figure_predictor.py

import plotly.graph_objects as go
import pandas as pd


def create_prediction_figure(df: pd.DataFrame):
    """
    根据从数据库读取的预测数据 DataFrame 创建 Plotly 图表。

    Args:
        df (pd.DataFrame): 未来预测数据的 DataFrame。

    Returns:
        go.Figure: 包含价格预测和注释的 Plotly 图表对象。
    """
    if df.empty:
        return go.Figure().update_layout(
            title='数据为空，无法生成预测图表。',
            template='plotly_while'
        )

    prediction_data = df.copy()

    # 从第一条数据中获取 prediction_time
    prediction_time = prediction_data.iloc[0].get('prediction_time')

    fig = go.Figure()

    # 绘制预测价格线
    if not prediction_data.empty:
        fig.add_trace(go.Scatter(
            x=prediction_data['close_time'],
            y=prediction_data['predicted_price'],
            mode='lines+markers',
            name='未来价格路径 (预测)',
            line=dict(color='#a3be8c', width=2),
            marker=dict(size=6, color='#a3be8c')
        ))

    # 更新图表布局
    fig.update_layout(
        xaxis_title_text='日期',
        yaxis_title_text='价格 (USD)',
        template='plotly_white',
        height=400, # 确保高度一致
        margin=dict(l=40, r=40, t=50, b=40),
        annotations=[
            go.layout.Annotation(
                text='此数据为模型预测结果，仅供参考。',
                xref="paper", yref="paper",
                x=0.5, y=1.05,
                xanchor='center',
                yanchor='bottom',
                showarrow=False,
                font=dict(size=14, color='#bd93f9')
            )
        ]
    )

    # 添加新的注释，显示预测时间
    if pd.notna(prediction_time):
        if isinstance(prediction_time, str):
            prediction_time = pd.to_datetime(prediction_time)

        time_text = prediction_time.strftime("%Y-%m-%d %H:%M:%S")

        fig.add_annotation(
            text=f'数据生成时间：{time_text}',
            xref="paper", yref="paper",
            x=1, y=0,
            xanchor='right', yanchor='bottom',
            font=dict(size=12, color="black"),
            showarrow=False,
            bgcolor="white",
            bordercolor="#d8dee9",
        )

    return fig