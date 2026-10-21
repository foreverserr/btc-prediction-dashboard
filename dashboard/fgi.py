# dashboard/fgi.py

import dash
from dash import dcc, html, Input, Output, callback, no_update
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import datetime
import io
from flask_login import current_user # 导入认证对象

# 导入外部模块
from db import get_historical_fgi_data  # 用于获取数据的 DB 函数
from figure.figure_fgi import get_fgi_traces, get_fgi_layout  # 用于绘图的函数

# 定义最小数据范围
MIN_DAYS_SPAN = 6

def get_unauthorized_figure(title_text="请重新登录以查看图表"):
    """生成一个标准的 Plotly 图形对象，包含未认证警告。"""
    return go.Figure().update_layout(
        title=title_text,
        template='plotly_while',
        height=400,
        annotations=[
            dict(
                text="用户认证信息失效，请刷新页面或重新登录。",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=20, color="#dc3545")
            )
        ]
    )


def get_fgi_card():
    """
    返回 FGI 独立图表所需的完整布局组件，
    包含 Store 和 Interval 组件，用于后台数据获取和绘图。
    """
    return html.Div(children=[
        dbc.Card(className='shadow-sm h-100', children=[
            dbc.CardHeader("近7天恐惧贪婪指数图", className='text-center fw-bold'),
            dbc.CardBody(
                dcc.Loading(
                    dcc.Graph(
                        id='fgi-standalone-chart',
                        figure=go.Figure().update_layout(title='载入中...', template='plotly_dark', height=400),
                        config={'displayModeBar': False}
                    )
                )
            )
        ]),

        # 内部 Store 组件，用于存储 FGI 数据
        dcc.Store(id='fgi-card-data-store'),

        # 内部 Interval 组件，触发 FGI 数据获取
        # 保持 5 分钟间隔
        dcc.Interval(
            id='fgi-card-interval',
            interval=300 * 1000,
            n_intervals=0
        )
    ])


# 回调函数：从数据库获取 FGI 数据并存储
@callback(
    Output('fgi-card-data-store', 'data'),
    [Input('fgi-card-interval', 'n_intervals'),]
)
def fetch_fgi_data(n_intervals_slow):
    """
    从数据库获取 FGI 历史数据并序列化存储。现在只由 fgi-card-interval 触发。
    在用户未认证时，阻止数据获取。
    """
    # 认证检查
    if not current_user.is_authenticated:
        return None

    # 如果不是由定时器触发，且不是初次加载
    ctx = dash.callback_context
    if not ctx.triggered:
        # 如果是初次加载，继续执行
        pass
    else:
        # 如果是定时器触发，打印信息
        # print("\n从数据库获取 FGI 数据")
        pass

    fgi_data = get_historical_fgi_data()

    if fgi_data.empty:
        print("错误: 从数据库获取到的 FGI 数据为空。")
        return {'error': '数据库中没有 FGI 数据。请检查后台同步脚本。'}

    # 将 DataFrame 转换为 JSON 格式
    return fgi_data.reset_index().rename(columns={'close_time': 'close_time_utc'}).to_json(orient='split',
                                                                                           date_format='iso')


# 根据存储的数据绘制 FGI 图表
@callback(
    Output('fgi-standalone-chart', 'figure'),
    Input('fgi-card-data-store', 'data')
)
def create_fgi_standalone_chart(stored_data):
    # 如果用户未认证，返回警告图表
    if not current_user.is_authenticated:
        return get_unauthorized_figure("FGI 情绪指数：未认证")

    if not stored_data:
        return go.Figure().update_layout(title='等待后台 FGI 数据...', template='plotly_dark', height=400)

    try:
        # 从 JSON 读回 DataFrame
        df = pd.read_json(io.StringIO(stored_data), orient='split')

        # 重新设置索引和类型
        df['close_time_utc'] = pd.to_datetime(df['close_time_utc']).dt.normalize()
        df.set_index('close_time_utc', inplace=True)
        fgi_df = df.astype({'FGI': float})

        # 筛选近七天数据
        start_date = datetime.date.today() - datetime.timedelta(days=MIN_DAYS_SPAN)
        filtered_df = fgi_df[fgi_df.index.date >= start_date].copy()

        if filtered_df.empty:
            return go.Figure().update_layout(title='FGI 过去7天数据为空', template='plotly_dark', height=400)

        fig = go.Figure()

        # 调用 figure/figure_fgi.py 中的绘图逻辑
        traces = get_fgi_traces(filtered_df)
        for trace in traces:
            fig.add_trace(trace)

        fig.layout = get_fgi_layout(filtered_df, fig.layout)

        fig.update_layout(
            title_text='',
            template='plotly_white',
            height=400,
            margin=dict(l=40, r=40, t=20, b=40),
            showlegend=False,
            hovermode="x unified"
        )

        fig.update_yaxes(
            range=[0, 100],
            fixedrange=True,
            title_text='FGI 指数',
            tickvals=[0, 25, 50, 75, 100],
            ticktext=['极度恐惧(0)', '恐惧(25)', '中立(50)', '贪婪(75)', '极度贪婪(100)'],
        )

        fig.update_xaxes(
            title_text='日期',
            tickformat='%m-%d',
            rangeslider_visible=False,
        )

        return fig

    except Exception as e:
        print(f"绘制 FGI 图表失败: {e}")
        return go.Figure().update_layout(title=f"FGI 绘图错误: {e}", template='plotly_dark', height=400)