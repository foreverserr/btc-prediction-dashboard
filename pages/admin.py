import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, callback, Input, Output

# 从解耦后的模块导入布局函数
from admin.user_management import create_user_management_layout
from admin.data_management import create_data_management_layout
from admin.log_management import create_log_management_layout

dash.register_page(__name__, path='/admin', name='后台管理')

# 通过导入函数创建各个部分
user_management_section = create_user_management_layout()
data_management_section = create_data_management_layout()
log_management_section = create_log_management_layout()

# 布局
layout = dbc.Container(
    [
        # 顶部导航栏
        dbc.Navbar(
            children=[
                dbc.Container(
                    children=[
                        # 1. 左侧：时间显示
                        html.Div(
                            [
                                html.Small(
                                    id='live-time-display-navbar',
                                    className='me-auto d-none d-lg-block',
                                    style={'color': '#000000'}  # 强制黑色
                                ),
                            ],
                            className="d-flex align-items-center me-auto"
                        ),

                        # 2. 中间：后台中心标题
                        dbc.NavbarBrand(
                            '后台中心',
                            className="mx-auto mb-0 fw-bold",
                            style={'color': '#000000'}
                        ),

                        # 3. 右侧：欢迎信息和注销按钮
                        html.Div(
                            [
                                html.Div(
                                    id='welcome-message-container',
                                    className="d-flex align-items-center me-3"
                                ),
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
            className="mb-4 shadow-sm"
        ),

        # 区域组件引用
        user_management_section,
        data_management_section,
        log_management_section,

        dcc.Location(id='url', refresh=True),
        dcc.Store(id='add-user-data-store', data=None),
        dcc.Store(id='change-password-user-store', data=None),
        dcc.Store(id='delete-user-store', data=None),
        dcc.Store(id='new-password-temp-store', data=None),

        # 用户管理相关的 Modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("确认添加新用户")),
            dbc.ModalBody(html.Div(id='add-modal-body')),
            dbc.ModalFooter([
                dbc.Button("取消", id="cancel-add-confirm-button", className="ms-auto", color="secondary", n_clicks=0),
                dbc.Button("确认添加", id="confirm-add-user-button", color="success", className="ms-3", n_clicks=0),
            ]),
        ], id="add-confirm-modal", is_open=False, centered=True),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(html.Div(id='change-pass-modal-title'))),
            dbc.ModalBody([
                html.Div(id='change-pass-alert'),
                html.Div(id='change-pass-alert-inner'),
                dbc.Form([
                    dbc.Label("新密码", html_for="new-password-change-input"),
                    dbc.Input(type="password", id="new-password-change-input", placeholder="请输入新密码",
                              className="mb-3"),
                    dbc.Label("确认新密码", html_for="confirm-password-change-input"),
                    dbc.Input(type="password", id="confirm-password-change-input", placeholder="请再次输入新密码",
                              className="mb-3"),
                ])
            ]),
            dbc.ModalFooter([
                dbc.Button("取消", id="cancel-password-change-button", className="ms-auto", color="secondary",
                           n_clicks=0),
                dbc.Button("确认", id="confirm-password-change-button", color="primary", className="ms-3",
                           n_clicks=0),
            ]),
        ], id="change-password-modal", is_open=False, centered=True),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("最终确认：修改密码")),
            dbc.ModalBody(html.Div(id='change-pass-final-confirm-body')),
            dbc.ModalFooter([
                dbc.Button("取消操作", id="cancel-final-password-change-button", className="ms-auto", color="secondary",
                           n_clicks=0),
                dbc.Button("确认修改", id="execute-password-change-button", color="danger", className="ms-3",
                           n_clicks=0),
            ]),
        ], id="change-pass-confirm-modal", is_open=False, centered=True),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("确认删除操作")),
            dbc.ModalBody(html.Div(id='delete-modal-body')),
            dbc.ModalFooter([
                dbc.Button("取消", id="cancel-delete-button", className="ms-auto", color="secondary", n_clicks=0),
                dbc.Button("确认删除", id="confirm-delete-button", color="danger", className="ms-3", n_clicks=0),
            ]),
        ], id="delete-confirm-modal", is_open=False, centered=True),

    ], fluid=True, className="min-vh-100"
)


# 控制用户管理页面的定时器开关
@callback(
    Output('users-interval', 'disabled'),
    Input('url', 'pathname')
)
def toggle_admin_intervals(pathname):
    """
    根据当前路径，控制用户管理定时器 (users-interval) 的启用和禁用。
    只有在 '/admin' 页面时，定时器才被启用 (disabled=False)。
    """
    if pathname == '/admin':
        return False # 启用定时器
    return True # 禁用定时器