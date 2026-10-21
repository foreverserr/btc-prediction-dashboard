# pages/login.py

import dash
from dash import html, dcc, callback, Input, Output, State, no_update
import dash_bootstrap_components as dbc
from flask_login import login_user
from flask import session
# 用户认证函数、SSO核心函数和日志函数
from db import get_user_by_username, verify_password, update_user_session_token, log_user_action

dash.register_page(__name__, path='/', name='用户登录')

layout = dbc.Container(
    [
        dcc.Location(id='url', refresh=True),

        dbc.Row(
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader(
                            html.H4(
                                "用户登录",
                                className="text-center fw-bold mb-0",
                                style={
                                    "color": "#000000",
                                    "backgroundColor": "#bbdefb",
                                    "border": "none",               # 强制去掉 Header 边框
                                    "borderRadius": "16px 16px 0 0"
                                }
                            ),
                            # 新增这行，强制去掉 CardHeader 自带的黑边框
                            style={"border": "none", "backgroundColor": "#bbdefb"}
                        ),
                        dbc.CardBody(
                            [
                                html.Div(id="login-alert-container", className="mb-3"),
                                dbc.Form(
                                    [
                                        dbc.Label("用户名",
                                                  html_for="username-input",
                                                  className="form-label fw-bold",
                                                  style={"color": "#000000"}),

                                        dbc.Input(
                                            type="text",
                                            id="username-input",
                                            placeholder="请输入用户名",
                                            className="mb-3"
                                        ),

                                        dbc.Label("密码",
                                                  html_for="password-input",
                                                  className="form-label fw-bold",
                                                  style={"color": "#000000"}),

                                        dbc.Input(
                                            type="password",
                                            id="password-input",
                                            placeholder="请输入密码",
                                            className="mb-3"
                                        ),

                                        dbc.Button(
                                            "登录",
                                            id="login-button",
                                            color="primary",
                                            className="mt-4 w-100 fw-bold",
                                            n_clicks=0,
                                            size="lg",
                                            style={"color": "#000"}
                                        ),
                                    ]
                                ),
                            ]
                        ),
                    ],
                    className="shadow",                    # 改成轻一点的 shadow
                    style={
                        "width": "420px",
                        "borderRadius": "16px",
                        "backgroundColor": "#e3f2fd",
                        "border": "none",                  # 再次强调去掉边框
                        "boxShadow": "0 15px 35px rgba(0, 0, 0, 0.1)",   # 柔和现代阴影
                        "overflow": "hidden"               # 防止边框溢出
                    },
                ),
                width=12,
                className="d-flex justify-content-center align-items-center vh-100"
            )
        )
    ],
    fluid=True,
    style={
        "backgroundColor": "#f0f7ff",
        "minHeight": "100vh",
        "padding": "0"
    }
)


@callback(
    Output('url', 'pathname', allow_duplicate=True),
    Output('login-alert-container', 'children'),
    Input('login-button', 'n_clicks'),
    State('username-input', 'value'),
    State('password-input', 'value'),
    prevent_initial_call=True
)
def handle_login(n_clicks, username, password):
    if n_clicks is None or n_clicks == 0:
        return no_update, no_update

    # 安全输入校验开始
    # 清理输入
    username = username.strip() if username else ''
    password = password.strip() if password else ''

    if not username or not password:
        # 日志记录用户名或密码为空的失败尝试
        log_user_action(
            operator=username if username else 'Anonymous',
            action_type='LOGIN',
            status='FAILURE',
            message='用户名或密码为空。'
        )
        return no_update, dbc.Alert("用户名或密码不能为空。", color="danger")

    # 检查非法字符 (防止 SQL 注入和恶意尝试)
    if not username.isalnum():
        # 日志记录尝试使用非法字符登录
        log_user_action(
            operator=username,
            action_type='LOGIN',
            status='FAILURE',
            message='用户名包含非法字符。'
        )
        return no_update, dbc.Alert("用户名或密码错误。", color="danger")

    # 阻止包含特殊字符的恶意尝试
    if not password.isalnum():
        # 尝试使用非法字符登录 (不记录密码内容)
        log_user_action(
            operator=username,
            action_type='LOGIN',
            status='FAILURE',
            message='密码包含非法字符。'
        )
        return no_update, dbc.Alert("用户名或密码错误。", color="danger")

    # 安全输入校验结束

    user = get_user_by_username(username)

    if user and verify_password(user, password):

        # 正常登录 Flask-Login
        login_user(user, remember=False)

        # 生成新的 Token 并写入数据库
        new_token = update_user_session_token(user.id)

        # 将新 Token 存入当前会话
        if new_token:
            session['session_token'] = new_token

        # 日志记录成功登录日志
        log_user_action(
            operator=username,
            action_type='LOGIN',
            status='SUCCESS',
            message='用户成功登录。'
        )

        # 登录成功，重定向到主页
        return "/dashboard", None

    else:
        # 日志记录失败登录尝试日志
        log_user_action(
            operator=username,
            action_type='LOGIN',
            status='FAILURE',
            message='用户名或密码错误。'
        )
        # 登录失败返回消息
        return no_update, dbc.Alert("用户名或密码错误。", color="danger")