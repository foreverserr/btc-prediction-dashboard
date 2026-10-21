# app.py

import dash
from dash import dcc, html, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
import datetime
from flask_login import LoginManager, UserMixin, current_user, logout_user
from dash import page_container, page_registry
from flask import redirect, request, session, flash
from datetime import timedelta
import dash_mantine_components as dmc
import pytz
import logging
import atexit

# 导入后台调度器
from apscheduler.schedulers.background import BackgroundScheduler
# from scipy.constants import minute

# 从 db 统一导入所需的函数、类和日志函数
from db import (
    get_user_by_id, setup_log_handlers, get_user_session_token, log_user_action
)
# 导入数据源函数
from fetch import get_initial_data, full_data_sync, sync_only_ticker , sync_daily_stats

# 导入模型启动函数
# from prediction.predict_offline import run_and_save_prediction

# 日志配置启动
setup_log_handlers()

# 数据检查同步配置启动
get_initial_data()
full_data_sync()
# run_and_save_prediction()

# 定义高频任务：仅同步价格
def fast_ticker_sync():
    try:
        sync_only_ticker('BTCUSDT')
    except Exception as e:
        logging.error(f"实时价格同步失败：{e}")

# 定义低频任务：同步历史K线和FGI
def slow_daily_sync():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        sync_daily_stats('BTCUSDT', '1d')
    except Exception as e:
        logging.error(f"每日数据同步失败：{e}")

# 配置调度器
scheduler = BackgroundScheduler(daemon=True)

# 每3秒同步一次实时价格
scheduler.add_job(fast_ticker_sync, 'interval', seconds=3, id='ticker_job')

# 每1小时同步一次 K 线和 FGI
scheduler.add_job(slow_daily_sync, 'interval', hours=1, id='daily_stats_job')
scheduler.start()

# 确保应用关闭时也关闭调度器
atexit.register(lambda: scheduler.shutdown())

# 创建 Dash 应用实例
app = dash.Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[dbc.themes.DARKLY],
    suppress_callback_exceptions=True
)

app.server.secret_key = 'helloworld'
app.server.permanent_session_lifetime = timedelta(hours=2)
# 下面是方便测试用户未认证的状态
# app.server.permanent_session_lifetime = timedelta(seconds=10)

server = app.server
login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = '/'


# 定义用户类 (不变)
class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role


@login_manager.user_loader
def load_user(user_id):
    if user_id is None:
        return None
    user_data = get_user_by_id(user_id)
    if user_data:
        return User(user_data['id'], user_data['username'], user_data['role'])
    return None

# 引入 404 处理器，解决 Dash SPA 状态码问题
# 强制返回 HTTP 404 状态码，确保 werkzeug 日志记录 404
@app.server.errorhandler(404)
def handle_404(err):
    """
    处理所有 Flask 认为找不到的 URL 请求。
    """
    path = request.path
    logging.warning(f"Dash SPA Path Not Registered: {path} -> Forcing 404 Status")
    return app.index(), 404

# 渲染 404 页面内容的回调
@app.callback(
    Output('page-container', 'children', allow_duplicate=True),
    [Input('url', 'pathname')],
    prevent_initial_call=True
)
def route_display(pathname):
    if pathname not in [page['path'] for page in page_registry.values()]:
        return html.Div([
            dmc.Center(
                dmc.Stack([
                    dmc.Title("404 页面未找到", order=1, c="red"),
                    dmc.Text(f"您访问的路径 '{pathname}' 不存在。", size="lg"),
                    dmc.Anchor("返回首页", href="/", size="lg")
                ], align="center"),
                style={'height': '80vh'}
            )
        ])
    return no_update

# 原有认证和用户逻辑

@app.server.before_request
def check_authentication():
    path = request.path
    ALLOWED_ADMIN_ROLES = ['admin', 'superadmin']
    if path.startswith('/_dash-') or path == '/favicon.ico':
        return None

    if current_user.is_authenticated:
        session_token = session.get('session_token')
        db_token = get_user_session_token(current_user.id)

        if db_token is not None and session_token != db_token:
            print(f"警告：用户 {current_user.username} 会话Token不匹配，强制注销。")

            log_user_action(
                operator=current_user.username,
                action_type='LOGOUT',
                status='FORCE',
                message='账号在其他设备登录。'
            )

            logout_user()
            session.clear()
            flash("您的账号已在其他设备上登录，当前会话已被强制注销。", 'danger')
            return redirect(login_manager.login_view)

        if path == login_manager.login_view:
            # print(f"用户已认证，自动重定向到 /dashboard")
            return redirect('/dashboard')

        if path == '/admin':
            if current_user.role not in ALLOWED_ADMIN_ROLES:
                # print(f"用户 {current_user.username} (角色: {current_user.role}) 无权访问 /admin，重定向到 /dashboard")
                return redirect('/dashboard')

        return None
    else:
        if path != login_manager.login_view:
            logout_user()
            # print(f"用户未认证，强制重定向到 {login_manager.login_view}")
            return redirect(login_manager.login_view)
        return None


@app.callback(
    Output('username-store', 'data', allow_duplicate=True),
    Input('url', 'pathname'),
    prevent_initial_call=True
)
def store_username(pathname):
    if current_user.is_authenticated and hasattr(current_user, 'username'):
        return {'username': current_user.username}
    return {'username': None}


@app.callback(
    Output('welcome-message-container', 'children'),
    Input('username-store', 'data'),
    prevent_initial_call=False
)
def update_welcome_message(data):
    if data and data.get('username'):
        username = data['username']
        return dmc.Text(f"欢迎您，{username}",
                        size="md",
                        c="dark",
                        fw=600,
                        className="me-3")
    return ""


@app.callback(
    Output('url', 'pathname', allow_duplicate=True),
    Output('logout-confirm-modal', 'opened', allow_duplicate=True),
    Input('logout-button', 'n_clicks'),
    Input('confirm-logout-button', 'n_clicks'),
    Input('cancel-logout-button', 'n_clicks'),
    State('logout-confirm-modal', 'opened'),
    prevent_initial_call=True
)
def process_global_logout(logout_n, confirm_n, cancel_n, is_opened):
    ctx = dash.callback_context
    if not ctx.triggered:
        return no_update, no_update
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if trigger_id == 'logout-button':
        if logout_n > 0 and not is_opened:
            return no_update, True
        return no_update, no_update
    if trigger_id == 'confirm-logout-button' and confirm_n and confirm_n > 0:

        if current_user.is_authenticated:
            log_user_action(
                operator=current_user.username,
                action_type='LOGOUT',
                status='SUCCESS',
                message='用户注销。'
            )

        logout_user()
        return '/', False
    if trigger_id == 'cancel-logout-button':
        return no_update, False
    return no_update, no_update


@app.callback(
    Output('live-time-display-navbar', 'children'),
    [Input('local-time-interval', 'n_intervals')]
)
def update_navbar_time(n_intervals):
    tz_taiwan = pytz.timezone('Asia/Taipei')
    now = datetime.datetime.now(tz_taiwan)
    formatted_time = now.strftime("%Y-%m-%d %H:%M:%S(UTC-8)")
    return formatted_time


# 3. 在主应用布局中添加 page_container 和全局 Modal
app.layout = dmc.MantineProvider(
    children=[
        dcc.Location(id='url', refresh=True),
        dcc.Store(id='username-store', data={'username': None}),
        dcc.Interval(id='local-time-interval', interval=1000, n_intervals=0),
        page_container,

        # 全局注销模态框
        dmc.Modal(
            title="确认注销",
            id="logout-confirm-modal",
            zIndex=10000,
            children=[
                dmc.Text("您确定要注销当前账户吗？注销后您将返回登录页面。", size="md"),
                dmc.Group(
                    [
                        dmc.Button("确定注销", id="confirm-logout-button", color="red", variant="filled", n_clicks=0),
                        dmc.Button("取消", id="cancel-logout-button", color="gray", variant="light", n_clicks=0),
                    ],
                    justify="flex-end",
                    mt="md",
                ),
            ],
            opened=False,
            withCloseButton=False
        ),
    ]
)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', threaded=True, port=80)