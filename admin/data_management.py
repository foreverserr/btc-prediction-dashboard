# admin/data_management.py

import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html, callback, Input, Output, State, no_update
from flask_login import current_user

from db import (
    get_latest_klines_df, get_latest_predictions_df,
    get_latest_realtime_ticker_df
)

FIVE_MINUTES_MS = 300000


def create_data_management_layout():

    data_management_layout = dbc.Card(
        [
            dbc.CardHeader(
                html.H4("数据管理中心", className="text-center fw-bold text-dark"),
                className="bg-dark"
            ),
            dbc.CardBody(
                dbc.Row([

                    # ================= K线数据 =================
                    dbc.Col(
                        dbc.Card([
                            dbc.CardHeader(
                                html.H4("历史K线数据", className="text-center fw-bold")
                            ),
                            dbc.CardBody([
                                html.Div(id="klines-data-table"),
                                dcc.Interval(
                                    id="klines-interval",
                                    interval=FIVE_MINUTES_MS,
                                    n_intervals=0
                                ),
                            ])
                        ], className="shadow-lg h-100 border-warning"),
                        lg=6, className="mb-4"
                    ),

                    # ================= 预测 + 实时 =================
                    dbc.Col(
                        dbc.Card([
                            dbc.CardHeader(
                                html.H4("预测与实时数据", className="text-center fw-bold")
                            ),
                            dbc.CardBody([

                                html.H5("预测价格数据", className="fw-bold text-success mt-1 text-center"),
                                html.Hr(className="my-2"),
                                html.Div(id="predictions-data-table", className="mb-4"),

                                html.H5("实时行情数据", className="fw-bold text-primary mt-3 text-center"),
                                html.Hr(className="my-2"),
                                html.Div(id="realtime-data-table-container", className="mb-3"),

                                dcc.Interval(
                                    id="predictions-interval",
                                    interval=FIVE_MINUTES_MS,
                                    n_intervals=0
                                ),
                                dcc.Interval(
                                    id="realtime-interval",
                                    interval=FIVE_MINUTES_MS,
                                    n_intervals=0
                                ),

                            ])
                        ], className="shadow-lg h-100 border-success"),
                        lg=6, className="mb-4"
                    )

                ], className="g-4"),
            ),
        ],
        className="mb-4 shadow-lg border-light bg-light text-dark"
    )

    return data_management_layout


# =========================================================
# K线数据
# =========================================================
@callback(
    Output("klines-data-table", "children"),
    Input("klines-interval", "n_intervals")
)
def update_klines_data_table(n):

    if not current_user.is_authenticated:
        return dbc.Alert("请登录以查看数据。", color="warning")

    symbol, interval = 'BTCUSDT', '1d'

    try:
        df_klines = get_latest_klines_df(symbol=symbol, interval=interval)

        if df_klines.empty:
            return dbc.Alert("klines_data 无数据", color="info")

        return dash_table.DataTable(
            id='klines-table',
            columns=[{"name": i, "id": i} for i in df_klines.columns],
            data=df_klines.to_dict('records'),

            style_header={
                'backgroundColor': '#cfdde6',
                'fontWeight': 'bold',
                'color': '#0f2f3f'
            },

            style_data={
                'backgroundColor': '#e8f0f5',
                'color': '#1f2d3a'
            },

            style_cell={
                'textAlign': 'center',
                'fontFamily': 'sans-serif',
                'border': '1px solid #c8d6e2'
            },

            page_action='native',
            page_size=15,
            style_table={'overflowX': 'auto'}
        )

    except Exception as e:
        print(f"Error fetching klines data: {e}")
        return dbc.Alert("加载 K 线数据失败", color="danger")


# =========================================================
# 预测数据
# =========================================================
@callback(
    Output("predictions-data-table", "children"),
    Input("predictions-interval", "n_intervals")
)
def update_predictions_data_table(n):

    if not current_user.is_authenticated:
        return dbc.Alert("请登录以查看数据。", color="warning")

    try:
        df_predictions = get_latest_predictions_df(symbol='BTCUSDT')

        if df_predictions.empty:
            return dbc.Alert("预测数据为空", color="info")

        return dash_table.DataTable(
            id='predictions-table',
            columns=[{"name": i, "id": i} for i in df_predictions.columns],
            data=df_predictions.to_dict('records'),

            style_header={
                'backgroundColor': '#cfdde6',
                'fontWeight': 'bold',
                'color': '#0f2f3f'
            },

            style_data={
                'backgroundColor': '#e8f0f5',
                'color': '#1f2d3a'
            },

            style_cell={
                'textAlign': 'center',
                'fontFamily': 'sans-serif',
                'fontSize': '12px',
                'border': '1px solid #c8d6e2'
            },

            page_action='native',
            page_size=10,
            style_table={'overflowX': 'auto'}
        )

    except Exception as e:
        print(f"Error fetching predictions data: {e}")
        return dbc.Alert("加载预测数据失败", color="danger")


# =========================================================
# 实时数据
# =========================================================
@callback(
    Output("realtime-data-table-container", "children"),
    Input("realtime-interval", "n_intervals")
)
def update_realtime_data_table(n):

    if not current_user.is_authenticated:
        return dbc.Alert("请登录以查看数据。", color="warning")

    try:
        df_realtime = get_latest_realtime_ticker_df()

        if df_realtime.empty:
            return dbc.Alert("实时数据为空", color="info")

        return dash_table.DataTable(
            id='realtime-table',
            columns=[{"name": i, "id": i} for i in df_realtime.columns],
            data=df_realtime.to_dict('records'),

            style_header={
                'backgroundColor': '#cfdde6',
                'fontWeight': 'bold',
                'color': '#0f2f3f'
            },

            style_data={
                'backgroundColor': '#e8f0f5',
                'color': '#1f2d3a'
            },

            style_cell={
                'textAlign': 'center',
                'fontFamily': 'sans-serif',
                'fontSize': '12px',
                'border': '1px solid #c8d6e2',
                'color': '#1f2d3a'
            },

            page_action='native',
            page_size=10,
            style_table={'overflowX': 'auto'}
        )

    except Exception as e:
        print(f"Error fetching realtime data: {e}")
        return dbc.Alert("加载实时数据失败", color="danger")