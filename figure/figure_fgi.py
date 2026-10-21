#figure/figure_fig.py
import plotly.graph_objects as go
import pandas as pd


def get_fgi_traces(df: pd.DataFrame) -> list:
    """
    获取恐惧与贪婪指数 (FGI) 的 Plotly 折线图 traces。
    FGI 折线图版本。
    """
    if df is None or df.empty or 'FGI' not in df.columns:
        return []

    traces = []
    traces.append(go.Scatter(
        x=df.index,
        y=df['FGI'],
        mode='lines+markers',  # 显示折线和数据点
        name='FGI (情绪指标)',
        line=dict(color='#00CC96', width=2),  # 绿色系折线
        marker=dict(size=6, line=dict(width=1, color='DarkSlateGrey')),
        # 优化悬停文本
        hovertemplate='日期: %{x|%Y-%m-%d}<br>FGI: %{y}<extra></extra>'
    ))

    return traces


def get_fgi_layout(df: pd.DataFrame, fig_layout: go.Layout) -> go.Layout:
    """
    设置 FGI 独立图表的布局（范围线和解释文本）。
    """
    if df.empty:
        return fig_layout

    # 获取索引的最小和最大时间，用于范围线的 x0, x1
    x_min = df.index.min()
    x_max = df.index.max()

    # 在独立图表中，x_ref 和 y_ref 默认为 "x" 和 "y"
    x_ref = "x"
    y_ref = "y"
    x_domain_ref = "x domain"
    y_domain_ref = "y domain"

    # 初始化形状和注释
    # 使用 tuple() 来确保结构兼容
    fig_layout.shapes = ()
    fig_layout.annotations = ()

    # 1. 添加极度贪婪线 (>75)
    fig_layout.shapes += (go.layout.Shape(
        type="line", x0=x_min, y0=75, x1=x_max, y1=75,
        line=dict(color="#FF00FF", width=1, dash="dot"),  # 使用鲜艳的颜色
        xref=x_ref, yref=y_ref
    ),)

    # 2. 添加极度恐惧线 (<25)
    fig_layout.shapes += (go.layout.Shape(
        type="line", x0=x_min, y0=25, x1=x_max, y1=25,
        line=dict(color="#00FFFF", width=1, dash="dot"),  # 使用鲜艳的颜色
        xref=x_ref, yref=y_ref
    ),)

    # 3. 添加解释文本
    fig_layout.annotations += (
        # 贪婪 (>75) 解释
        go.layout.Annotation(xref=x_domain_ref, yref=y_domain_ref, x=1.0, y=0.95,
                             text="极度贪婪 (>75)", showarrow=False, xanchor='right',
                             font=dict(color="#FF00FF", size=10)),
        # 恐惧 (<25) 解释
        go.layout.Annotation(xref=x_domain_ref, yref=y_domain_ref, x=1.0, y=0.05,
                             text="极度恐惧 (<25)", showarrow=False, xanchor='right',
                             font=dict(color="#00FFFF", size=10))
    )

    # 更新布局
    return fig_layout