# pages/dashboard.py

import dash
from dash import dcc, html, Input, Output, State, callback, no_update, Patch
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import datetime
import dash_mantine_components as dmc
from flask_login import current_user  # 核心导入：用于认证检查

# 导入用于获取所有历史数据的函数
from db import get_historical_klines_data

# 导入所有图表逻辑（全部从 dashboard 导入）
from dashboard.ma import get_ma_traces
from dashboard.macd import get_macd_traces_with_layout
from dashboard.daily_return import get_daily_return_traces
from dashboard.volume import get_volume_traces_with_layout
from dashboard.rsi import get_rsi_traces
from dashboard.bollinger_bands import get_bollinger_traces_with_layout
# K 线图解耦导入
from dashboard.kline_chart import get_pure_kline_trace

# 导入 FGI 独立卡片模块函数
from dashboard.fgi import get_fgi_card
# 导入预测函数
from dashboard.prediction import get_predictions
# 导入新的 Overview UI 函数
from dashboard.overview import get_overview_ui

# 注册页面
dash.register_page(__name__, path='/dashboard', name='综合仪表板')

# 定义日期范围的常量
min_date_allowed = datetime.date(2017, 8, 18)
max_date_allowed = datetime.date.today()
start_date_default = (datetime.date.today() - datetime.timedelta(days=90))
end_date_default = datetime.date.today()
MIN_DAYS_SPAN = 30


# 生成标准未认证警告图表
def get_unauthorized_figure(title_text="请重新登录以查看图表"):
    """
    生成一个标准的 Plotly 图形对象，包含未认证警告。
    """
    return go.Figure().update_layout(
        title=title_text,
        template='plotly_while',
        height=950,
        annotations=[
            dict(
                text="用户认证信息失效，请刷新页面或重新登录。",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=20, color="#dc3545")  # Bootstrap Danger Red
            )
        ]
    )


# 页面布局
layout = dbc.Container(
    fluid=True,
    children=[
        # 导航栏部分
        dbc.Navbar(
            children=[
                dbc.Container(
                    children=[
                        html.Small(
                            id='live-time-display-navbar',
                            className='me-auto d-none d-lg-block',
                            style={'color': '#000000'}  # 强制黑色
                        ),
                        dbc.NavbarBrand(
                            '比特币数据分析仪表板',
                            className="mx-auto mb-0 fw-bold",
                            style={'color': '#000000'}
                        ),
                        html.Div(
                            [
                                html.Div(id='welcome-message-container'),
                                dbc.Button(
                                    "注销",
                                    id="logout-button",
                                    n_clicks=0,
                                    color="danger",
                                    style={"color": "#000"}
                                ),
                            ],
                            className="d-flex align-items-center ms-auto",
                            style={'color': '#000000'}  # 强制黑色
                        ),
                    ],
                    className="d-flex align-items-center",
                    fluid=True
                )
            ],
            style={"z-index": 100}
        ),

        html.Div(id='dashboard-alert-container', className='mb-2'),

        # Store 组件
        dcc.Store(id='dashboard-data-store', data=None),
        dcc.Store(id='shared-historical-data', data=None),
        dcc.Store(id='shared-date-range', data=None),

        # 顶部实时数据概览 (包含 overview-interval-component)
        get_overview_ui(),

        dbc.Container(
            fluid=True,
            children=[
                dbc.Row([
                    dbc.Col(
                        html.Div(id='date-alert-container'),
                        width=12,
                        className="d-flex justify-content-center mt-2"
                    )
                ]),
            ],
            className='my-4'
        ),

        dbc.Row(className='g-2 align-items-stretch my-4', children=[
            dbc.Col([
                dbc.Card(className='mb-4 shadow-sm h-100', children=[
                    dbc.CardHeader("技术指标分析", className='text-center fw-bold'),
                    dbc.CardBody(
                        [
                            # 日期选择器 (保持不变)
                            html.Div(className='d-flex flex-wrap align-items-center justify-content-center mb-3',
                                     children=[
                                         html.Label("数据日期范围：", className="me-3 fw-bold align-self-center",  style={'color': '#000000'}),
                                         dmc.DatePickerInput(
                                             id='start-date-input',
                                             value=start_date_default,
                                             minDate=min_date_allowed,
                                             maxDate=max_date_allowed,
                                             placeholder="开始日期",
                                             style={"width": 150},
                                             dropdownType='popover',
                                             valueFormat='YYYY年MM月DD日'
                                         ),
                                         html.Span(' ~ ', className="mx-2 align-self-center",  style={'color': '#000000'}),
                                         dmc.DatePickerInput(
                                             id='end-date-input',
                                             value=end_date_default,
                                             minDate=min_date_allowed,
                                             maxDate=max_date_allowed,
                                             placeholder="结束日期",
                                             style={"width": 150},
                                             dropdownType='popover',
                                             valueFormat='YYYY年MM月DD日'
                                         ),
                                     ]),
                            # 多合一图表
                            dcc.Loading(
                                html.Div(
                                    dcc.Graph(
                                        id='all-in-one-chart',
                                        figure=go.Figure().update_layout(title='数据载入中...', template='plotly_dark'),
                                        config={'scrollZoom': True},
                                        style={'height': '900px'}
                                    ),
                                    style={'height': '900px'}
                                )
                            )
                        ]
                    )
                ]),
            ], md=12),
        ]),

        # --- 第二个主要区域：FGI 独立图表 (左) 和 价格预测 (右) ---
        dbc.Row(className='g-4 align-items-stretch my-4', children=[
            dbc.Col(get_fgi_card(), md=6),
            dbc.Col(get_predictions(), md=6),
        ]),

        # 确保 dcc.Location 在布局中
        dcc.Location(id='url', refresh=True),

        # 局部更新定时器
        dcc.Interval(
            id='interval-kline-local-update',
            interval=1800 * 1000,
            n_intervals=0
        ),
    ]
)

# 负责更新“历史/技术指标”数据（仅在初次进入页面时触发一次）
@callback(
    Output('shared-historical-data', 'data'),
    Input('url', 'pathname'),  # 监听路径变化，进入 dashboard 时加载一次
    prevent_initial_call=False
)
def load_historical_data_once(pathname):
    if pathname != '/dashboard' or not current_user.is_authenticated:
        return no_update

    try:
        # 这是一个耗时且庞大的操作，不再随 5 分钟定时器刷新
        historical_data = get_historical_klines_data()
        historical_data_dict = historical_data.to_dict('records') if not historical_data.empty else []
        return historical_data_dict
    except Exception as e:
        print(f"历史数据加载异常: {e}")
        return []


@callback(
    Output('shared-date-range', 'data'),
    [Input('start-date-input', 'value'),
     Input('end-date-input', 'value')]
)
def update_shared_date_range(start_date_str, end_date_str):
    if not start_date_str or not end_date_str:
        return dash.no_update

    start_date = datetime.date.fromisoformat(start_date_str)
    end_date = datetime.date.fromisoformat(end_date_str)

    if start_date > end_date:
        return dash.no_update

    time_delta = (end_date - start_date).days
    if time_delta < MIN_DAYS_SPAN - 1:
        return dash.no_update

    return [start_date_str, end_date_str]


@callback(
    Output('date-alert-container', 'children'),
    [Input('start-date-input', 'value'),
     Input('end-date-input', 'value')]
)
def display_date_range_alert(start_date_str, end_date_str):
    if not start_date_str or not end_date_str:
        return None

    start_date = datetime.date.fromisoformat(start_date_str)
    end_date = datetime.date.fromisoformat(end_date_str)

    if start_date > end_date:
        alert = dbc.Alert(
            "开始日期不能晚于结束日期。",
            color="danger",
            className="p-2 text-center"
        )
        return alert

    time_delta = (end_date - start_date).days
    if time_delta < MIN_DAYS_SPAN - 1:
        alert = dbc.Alert(
            f"日期范围必须至少包含 {MIN_DAYS_SPAN} 天的数据。",
            color="warning",
            className="p-2 text-center"
        )
        return alert

    return None


@callback(
    Output('dashboard-data-store', 'data'),
    [Input('shared-historical-data', 'data'),
     Input('shared-date-range', 'data')],
    prevent_initial_call=False
)
def filter_and_resample_historical_data(all_historical_data, date_range):
    if not current_user.is_authenticated or not all_historical_data or not date_range:
        return []

    df = pd.DataFrame(all_historical_data)
    df['open_time'] = pd.to_datetime(df['open_time'])
    df.set_index('open_time', inplace=True)
    df = df.astype({'open': float, 'high': float, 'low': float, 'close': float, 'volume': float})

    start_date = pd.to_datetime(date_range[0])
    end_date = pd.to_datetime(date_range[1])
    filtered_df = df[(df.index.date >= start_date.date()) & (df.index.date <= end_date.date())].copy()

    if filtered_df.empty:
        return []

    time_delta = (end_date - start_date).days

    if time_delta >= 1095:
        resample_freq = 'ME'
        # 采样后点数少于 12 个则降级为周线
        if len(filtered_df.resample('ME').size()) < 12:
            resample_freq = 'W'

    elif time_delta >= 365:
        resample_freq = 'W'
        # 采样后点数少于 40 个（约 9 个月数据）则降级为日线（None）
        if len(filtered_df.resample('W').size()) < 40:
            resample_freq = None

    else:
        resample_freq = None  # 不重采样，保持日线

    # --- 执行采样 ---
    if resample_freq:
        df_to_return = filtered_df.resample(resample_freq).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
    else:
        df_to_return = filtered_df

    return df_to_return.reset_index().to_dict('records')


@callback(
    Output('all-in-one-chart', 'figure'),
    [Input('dashboard-data-store', 'data'),
     Input('interval-kline-local-update', 'n_intervals')],
    prevent_initial_call=False
)
def create_composite_chart(data_state,n_intervals):
    """
    创建复合技术指标图表。在用户未认证时，显示警告信息。
    """
    # 认证检查：如果用户未认证，返回警告图表
    if not current_user.is_authenticated:
        return get_unauthorized_figure("技术指标分析：未认证")

    if not data_state or len(data_state) < 2:
        return go.Figure().update_layout(title='暂无数据或数据量不足', template='plotly_dark')

    df = pd.DataFrame(data_state)
    df['open_time'] = pd.to_datetime(df['open_time'])
    df.set_index('open_time', inplace=True)
    df = df.astype({'open': float, 'high': float, 'low': float, 'close': float, 'volume': float})

    rsi_windows = [7, 14, 21]
    bollinger_params = [(20, 2), (10, 1), (30, 3)]

    # 布局配置: 5 行，按 K线 -> Volume -> MACD -> Return -> RSI 顺序
    fig = make_subplots(
        rows=5, cols=1,
        row_heights=[0.4, 0.15, 0.15, 0.15, 0.15],
        shared_xaxes=True,
        vertical_spacing=0.02
    )

    # Row 1：主图：K线图 + 均线 + 布林带

    # K线 Trace
    kline_traces = get_pure_kline_trace(df)
    for trace in kline_traces:
        trace.name = 'K线图'
        trace.hoverinfo = 'all'
        fig.add_trace(trace, row=1, col=1)

    # MA 均线
    ma_traces = get_ma_traces(df)
    for trace in ma_traces:
        if trace.name != 'MA (10日)':
            trace.visible = 'legendonly'
        fig.add_trace(trace, row=1, col=1)

    # 布林带
    for period, stddev in bollinger_params:
        if len(df) >= period:
            bollinger_traces = get_bollinger_traces_with_layout(df.copy(), period, stddev)

            for trace in bollinger_traces:
                pass # 保留 trace.hoverinfo 默认值

            if period != 20 or stddev != 2:
                for trace in bollinger_traces:
                    trace.visible = 'legendonly'

            for trace in bollinger_traces:
                fig.add_trace(trace, row=1, col=1)

    # Row 2 - 交易量 (Volume)
    volume_traces = get_volume_traces_with_layout(df)
    for trace in volume_traces:
        fig.add_trace(trace, row=2, col=1)

    # Row 3 - MACD
    macd_traces = get_macd_traces_with_layout(df)
    for trace in macd_traces:
        fig.add_trace(trace, row=3, col=1)

    fig.add_annotation(xref="x3 domain", yref="y3 domain", x=1.0, y=0.9,
                       text="上方: 上涨动能增强", showarrow=False, xanchor='right',
                       font=dict(color="rgba(255, 255, 255, 0.6)", size=10), row=3, col=1)
    fig.add_annotation(xref="x3 domain", yref="y3 domain", x=1.0, y=0.1,
                       text="下方: 下跌动能增强", showarrow=False, xanchor='right',
                       font=dict(color="rgba(255, 255, 255, 0.6)", size=10), row=3, col=1)

    # Row 4 - 每日回报率
    daily_return_traces = get_daily_return_traces(df)
    for trace in daily_return_traces:
        fig.add_trace(trace, row=4, col=1)

    # 调整每日回报率注释的行引用：xref="x4 domain", yref="y4 domain"
    fig.add_annotation(xref="x4 domain", yref="y4 domain", x=1.0, y=0.9,
                       text="上方: 价格上涨", showarrow=False, xanchor='right',
                       font=dict(color="rgba(255, 255, 255, 0.6)", size=10), row=4, col=1)
    fig.add_annotation(xref="x4 domain", yref="y4 domain", x=1.0, y=0.1,
                       text="下方: 价格下跌", showarrow=False, xanchor='right',
                       font=dict(color="rgba(255, 255, 255, 0.6)", size=10), row=4, col=1)

    # Row 5 - RSI 指数
    for window in rsi_windows:
        if len(df) >= window:
            rsi_traces = get_rsi_traces(df.copy(), window)
            for trace in rsi_traces:
                trace.name = f'RSI ({window}日)'
                if window != 14:
                    trace.visible = 'legendonly'
                fig.add_trace(trace, row=5, col=1)

    # 调整 RSI 辅助线、Y轴和注释的行引用
    fig.add_shape(type="line", x0=df.index.min(), y0=70, x1=df.index.max(), y1=70,
                  line=dict(color="red", width=1, dash="dot"), xref="x5", yref="y5", row=5,
                  col=1)
    fig.add_shape(type="line", x0=df.index.min(), y0=30, x1=df.index.max(), y1=30,
                  line=dict(color="green", width=1, dash="dot"), xref="x5", yref="y5", row=5,
                  col=1)
    fig.update_yaxes(range=[0, 100], fixedrange=True, title_text='RSI', row=5, col=1)

    fig.add_annotation(xref="x5 domain", yref="y5 domain", x=1.0, y=0.95,
                       text="超买区", showarrow=False, xanchor='right',
                       font=dict(color="red", size=10), row=5, col=1)
    fig.add_annotation(xref="x5 domain", yref="y5 domain", x=1.0, y=0.05,
                       text="超卖区", showarrow=False, xanchor='right',
                       font=dict(color="green", size=10), row=5, col=1)

    # --- 添加最高价和最低价标记 (在 Row 1 ) ---
    if not df.empty:
        max_high_price = df['high'].max()
        min_low_price = df['low'].min()
        max_high_time = df['high'].idxmax()
        min_low_time = df['low'].idxmin()

        fig.add_annotation(
            x=max_high_time,
            y=max_high_price,
            xref="x1", yref="y1",
            text=f"最高价: ${max_high_price:,.2f}",
            showarrow=True,
            arrowhead=2,
            arrowcolor="white",
            ax=0,
            ay=-40
        )

        fig.add_annotation(
            x=min_low_time,
            y=min_low_price,
            xref="x1", yref="y1",
            text=f"最低价: ${min_low_price:,.2f}",
            showarrow=True,
            arrowhead=2,
            arrowcolor="white",
            ax=0,
            ay=40
        )

    # X轴同步
    fig.update_xaxes(
        rangeslider_visible=False,
        showticklabels=False,
        matches='x',
        row=1, col=1
    )
    fig.update_xaxes(
        rangeslider_visible=False,
        showticklabels=False,
        matches='x',
        row=2, col=1  # 交易量
    )
    fig.update_xaxes(
        rangeslider_visible=False,
        showticklabels=False,
        matches='x',
        row=3, col=1  # MACD
    )
    fig.update_xaxes(
        rangeslider_visible=False,
        showticklabels=False,
        matches='x',
        row=4, col=1  # 每日回报率
    )
    fig.update_xaxes(
        rangeslider_visible=False,
        matches='x',
        row=5, col=1  # RSI
    )

    fig.update_layout(
        title_text='',
        template='plotly_white',
        hovermode='x',

        xaxis_showgrid=False,
        yaxis_showgrid=False,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.02,
            tracegroupgap=5,
        ),
        # 调整 Y 轴引用与 Row 对应
        yaxis=dict(fixedrange=True),  # Row 1 (Price)
        yaxis2=dict(autorange=True),  # Row 2 (Volume)
        yaxis3=dict(autorange=True),  # Row 3 (MACD)
        yaxis4=dict(autorange=True),  # Row 4 (Daily Return)
        yaxis5=dict(autorange=True),  # Row 5 (RSI)

        margin=dict(l=80, r=20, t=60, b=20),
    )

    # 调整 Y 轴标题的 Row 引用
    fig.update_yaxes(title_text="价格 ($)", row=1, col=1)
    fig.update_yaxes(title_text="交易量 (BTC)", row=2, col=1)
    fig.update_yaxes(title_text="MACD 值", row=3, col=1)
    fig.update_yaxes(title_text="每日回报 (%)", row=4, col=1)
    fig.update_yaxes(title_text="RSI 指数", row=5, col=1)

    return fig

