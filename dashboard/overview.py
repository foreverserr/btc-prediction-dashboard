# dashboard/overview.py

from dash import html, Input, Output, callback, dcc, no_update
import dash_bootstrap_components as dbc
from db import get_latest_realtime_ticker
from flask_login import current_user
import datetime

def get_overview_ui():
    return html.Div([
        dcc.Interval(
            id='overview-interval-component',
            interval=1 * 1000,
            n_intervals=0,
            disabled=False
        ),
        dbc.Row(className='my-4', children=[
            dbc.Col(
                dbc.Card(className='shadow-sm h-100', children=[
                    dbc.CardHeader("当天市场数据", className='text-center fw-bold'),
                    dbc.CardBody(
                        dbc.Row(className='g-2', children=[
                            dbc.Col(create_status_card("最新价格", "dashboard-live-price"), lg=2, md=4, sm=6),
                            dbc.Col(create_status_card("变化", "dashboard-24h-change"), lg=2, md=4, sm=6),
                            dbc.Col(create_status_card("开盘价", "dashboard-open-price"), lg=2, md=4, sm=6),
                            dbc.Col(create_status_card("最高价", "dashboard-24h-high-price"), lg=2, md=4, sm=6),
                            dbc.Col(create_status_card("最低价", "dashboard-24h-low-price"), lg=2, md=4, sm=6),
                            dbc.Col(create_status_card("交易量", "dashboard-24h-volume"), lg=2, md=4, sm=6),
                        ])
                    )
                ]), width=12)
        ])
    ])

def create_status_card(label, element_id):
    return dbc.Card([
        dbc.CardHeader(label, className='text-center'),
        html.P('载入中...', id=element_id, className='fs-5 fw-bold')
    ], className='text-center bg-dark text-white shadow-sm h-100')

@callback(
    Output('overview-interval-component', 'disabled'),
    Input('url', 'pathname')
)
def toggle_overview_timer(pathname):
    return pathname != '/dashboard'

@callback(
    [Output('dashboard-live-price', 'children'),
     Output('dashboard-24h-change', 'children'),
     Output('dashboard-open-price', 'children'),
     Output('dashboard-24h-high-price', 'children'),
     Output('dashboard-24h-low-price', 'children'),
     Output('dashboard-24h-volume', 'children')],
    [Input('overview-interval-component', 'n_intervals')],
    prevent_initial_call=False
)
def update_overview_ui_from_db(n_intervals):
    import datetime
    current_time = datetime.datetime.now().strftime("%H:%M:%S")

    if not current_user.is_authenticated:
        return [html.Span('请登录', className='text-danger fw-bold')] * 6

    overview_data = get_latest_realtime_ticker(symbol='BTCUSDT')
    if not overview_data:
        print(f"[{current_time}] 未获取到数据库数据")
        return ('N/A', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A')

    # 提取所有数据
    price = float(overview_data.get('lastPrice', 0.0))
    change = float(overview_data.get('priceChangePercent', 0.0))
    open_p = float(overview_data.get('openPrice', 0.0))
    high_p = float(overview_data.get('highPrice', 0.0))
    low_p = float(overview_data.get('lowPrice', 0.0))
    vol = float(overview_data.get('volume', 0.0))

    # # 打印全部展示数据（测试是否有刷新）
    # print(f"--- [{current_time}] 实时概览刷新 (第 {n_intervals} 次) ---")
    # print(f"最新: ${price:,.2f} | 幅度: {change:+.2f}%")
    # print(f"开盘: ${open_p:,.2f} | 最高: ${high_p:,.2f} | 最低: ${low_p:,.2f}")
    # print(f"成交量: {vol:,.0f}")
    # print(f"-----------------------------------------------")

    color = 'green' if change > 0 else 'red' if change < 0 else 'white'

    return (
        f"${price:,.2f}",
        html.Span(f"{change:+.2f}%", style={'color': color}),
        f"${open_p:,.2f}",
        f"${high_p:,.2f}",
        f"${low_p:,.2f}",
        f"{vol:,.0f}"
    )