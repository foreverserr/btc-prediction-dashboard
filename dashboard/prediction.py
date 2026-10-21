# dashboard/prediction.py (价格预测模块)

import dash
from dash import dcc, html, Input, Output, callback
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
import pandas as pd
import io
from flask_login import current_user # 导入认证对象
from db import get_predictions_data_from_db
from figure import create_prediction_figure

def get_unauthorized_figure(title_text="请重新登录以查看图表"):
    """生成一个标准的 Plotly 图形对象，包含未认证警告。"""
    return go.Figure().update_layout(
        title=title_text,
        template='plotly_while',
        height=400, # 配合预测图表原始高度
        annotations=[
            dict(
                text="用户认证信息失效，请刷新页面或重新登录。",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=20, color="#dc3545") # Bootstrap Danger Red
            )
        ]
    )

def get_predictions():
    """
    返回预测页面所需的完整布局组件，
    包含一个回调函数来从数据库获取数据并绘图。
    """
    return html.Div(children=[
        dbc.Row([
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader("未来7日价格预测图", className='text-center'),
                    dbc.CardBody(dcc.Loading(
                        dcc.Graph(
                            id='prediction-graph',
                            style={'height': '400px'},
                            figure=go.Figure().update_layout(title='正在加载预测数据...', template='plotly_dark')
                        )
                    ))
                ], className='bg-dark text-white shadow-sm'),
                md=12
            ),
        ], className='g-4'),

        # 这个 store 用于存储筛选后的数据
        dcc.Store(id='prediction-data-store'),

        # 使用 Interval 组件每隔一段时间刷新图表，保持 5 分钟间隔
        dcc.Interval(
            id='prediction-interval',
            interval=5 * 60 * 1000,
            n_intervals=0
        )
    ])


# 回调函数：从数据库读取数据并存储
@callback(
    Output('prediction-data-store', 'data'),
    [Input('prediction-interval', 'n_intervals'),]
)
def fetch_prediction_data(n_intervals_slow):
    """
    从数据库获取预测数据并存储。现在只由 prediction-interval 触发。
    在用户未认证时，阻止数据获取。
    """
    # 认证检查
    if not current_user.is_authenticated:
        return None

    # print("从数据库获取预测数据")
    df = get_predictions_data_from_db()

    if df.empty:
        print("从数据库获取到的预测数据为空。")
        return {'数据库中没有预测数据。请运行后台预测脚本。'}

    # 将 DataFrame 转换为 JSON 格式以便存储在 dcc.Store 中
    return df.to_json(orient='split', date_format='iso')


# 回调函数：根据存储的数据绘制图表 (保持不变)
@callback(
    Output('prediction-graph', 'figure'),
    Input('prediction-data-store', 'data')
)
def update_prediction_graph(stored_data):
    # 认证检查：如果用户未认证，返回警告图表
    if not current_user.is_authenticated:
        return get_unauthorized_figure("价格预测：未认证")

    if not stored_data:
        return go.Figure().update_layout(title='等待后台数据...', template='plotly_dark')

    try:
        # 从 JSON 读回 DataFrame
        df = pd.read_json(io.StringIO(stored_data), orient='split')
        df['close_time'] = pd.to_datetime(df['close_time'])

        # 调用 figure_predictor.py 中的函数来创建图表
        fig = create_prediction_figure(df)

        return fig

    except Exception as e:
        print(f"绘制预测图表失败: {e}")
        return go.Figure().update_layout(title=f"绘图错误: {e}", template='plotly_dark')