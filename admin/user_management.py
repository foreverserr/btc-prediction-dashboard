import dash
import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html, callback, Input, Output, State, no_update
from flask_login import current_user
from db import (
    get_all_users, add_user, delete_user, update_user_password, log_action
)

# 布局定义
def create_user_management_layout():
    """
    创建系统用户管理区域的布局。
    """
    user_management_layout = dbc.Card(
        [
            # 卡片头部：系统用户管理
            dbc.CardHeader(
                html.H4("系统用户管理", className="text-center fw-bold text-dark"),
                className="bg-light"
            ),
            dbc.CardBody(
                dbc.Row([
                    # 用户列表表格
                    dbc.Col(
                        dbc.Card([
                            dbc.CardHeader(html.H4("系统用户列表", className="text-center fw-bold")),
                            dbc.CardBody([
                                html.Div(id="table-operation-alert", className="mb-3"),
                                html.Div(id="user-table-container"),
                                dcc.Interval(id="users-interval", interval=5000, disabled=True)
                            ])
                        ], className="shadow-lg h-100 border-info"), lg=8, className="mb-4"
                    ),
                    # 添加新用户表单
                    dbc.Col(
                        dbc.Card([
                            dbc.CardHeader(html.H4("添加新用户", className="text-center fw-bold")),
                            dbc.CardBody([
                                html.Div(id="add-user-alert"),
                                dbc.Form([
                                    dbc.Label("用户名", html_for="new-username-input", style={"color": "#1f2d3a"}),
                                    dbc.Input(type="text", id="new-username-input", placeholder="请输入用户名",
                                              className="mb-3", debounce=True),
                                    dbc.Label("密码", html_for="new-password-input", style={"color": "#1f2d3a"}),
                                    dbc.Input(type="password", id="new-password-input", placeholder="请输入密码",
                                              className="mb-3"),
                                    dbc.Label("角色", html_for="new-role-input", style={"color": "#1f2d3a"}),
                                    dcc.Dropdown(id="new-role-input", options=[], value='user',
                                                 className="mb-4 text-dark"),
                                    dbc.Button("添加用户", id="add-user-button", color="primary", className="w-100",
                                               n_clicks=0),
                                ])
                            ])
                        ], className="shadow-lg h-100 border-success"), lg=4, className="mb-4"
                    )
                ], className="g-4"),
                className="p-4"
            ),
        ],
        className="mb-4 shadow-lg border-light bg-light text-dark"
    )
    return user_management_layout

# 用户管理回调
@callback(Output("user-table-container", "children"), Input("users-interval", "n_intervals"))
def update_user_table(n):
    if not current_user.is_authenticated or current_user.role not in ['admin', 'superadmin']:
        return dbc.Alert("您没有访问该页面的权限。", color="danger")
    try:
        users_df = get_all_users()
    except Exception as e:
        print(f"Error fetching users: {e}")
        return dbc.Alert("加载用户数据失败，请检查数据库连接。", color="danger")
    if users_df.empty:
        return dbc.Alert("没有找到用户。", color="info")

    # 权限过滤逻辑
    is_super_admin_user = current_user.username == 'admin'
    users_df = users_df[users_df['username'] != current_user.username]
    if not is_super_admin_user:
        users_df = users_df[users_df['username'] != 'admin']
        if current_user.role == 'admin':
            users_df = users_df[users_df['role'] == 'user']
    if users_df.empty:
        return dbc.Alert("没有其他用户可供管理。", color="info")
    columns = [{"name": i, "id": i} for i in users_df.columns if i not in ['password_hash']]
    columns.extend([{"name": "修改密码", "id": "change_pass"}, {"name": "删除", "id": "delete_btn"}])
    data = users_df.to_dict('records')
    for row in data:
        row['change_pass'] = '📝'
        row['delete_btn'] = '🗑️'
    table = dash_table.DataTable(
        id='user-table',
        columns=columns,
        data=data,
        row_deletable=False,
        page_action='native',
        page_size=10,
        style_table={'overflowX': 'auto'},
        style_cell={
            'textAlign': 'center',  # 使所有单元格内容居中
            'minWidth': '80px', 'width': '120px', 'maxWidth': '180px',
            'textOverflow': 'ellipsis',
            'overflow': 'hidden',
        },
        css=[
            {"selector": ".dash-table-container", "rule": "font-family: sans-serif;"},
            {"selector": ".dash-table-container .row-index", "rule": "text-align: center;"},
        ]
    )
    return table

@callback(Output("new-role-input", "options"), Output("new-role-input", "value"),
          Input("users-interval", "n_intervals"))
def update_add_user_roles(n):
    if not current_user.is_authenticated or current_user.role not in ['admin', 'superadmin']:
        return no_update, no_update
    is_super_admin = current_user.role == 'superadmin'
    options = [{'label': '普通用户', 'value': 'user'}]
    if is_super_admin:
        options.append({'label': '管理员', 'value': 'admin'})
    return options, 'user'

@callback(
    # Outputs
    Output("add-confirm-modal", "is_open"),
    Output("add-modal-body", "children"),
    Output("add-user-data-store", "data"),
    Output("add-user-alert", "children", allow_duplicate=True),
    Output("users-interval", "n_intervals", allow_duplicate=True),
    Output("new-username-input", "value"),
    Output("new-password-input", "value"),

    # Inputs (按钮)
    Input("add-user-button", "n_clicks"),
    Input("confirm-add-user-button", "n_clicks"),
    Input("cancel-add-confirm-button", "n_clicks"),

    # States (表单/存储)
    State("new-username-input", "value"),
    State("new-password-input", "value"),
    State("new-role-input", "value"),
    State("add-user-data-store", "data"),
    prevent_initial_call=True
)
def handle_add_user_flow(add_n, confirm_n, cancel_n, username, password, role, store_data):
    ctx = dash.callback_context
    if not ctx.triggered: return no_update, no_update, no_update, no_update, no_update, no_update, no_update
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    operator, action_type = current_user.username, 'ADD_USER'
    clear_inputs = '', ''

    # 辅助函数：生成并返回错误警告
    def validation_error(message):
        return False, no_update, None, dbc.Alert(message, color="danger"), no_update, no_update, no_update

    # 触发源：取消按钮 (关闭 Modal)
    if trigger_id == 'cancel-add-confirm-button':
        return False, no_update, None, no_update, no_update, no_update, no_update

    # 触发源：添加用户按钮 (验证并打开 Modal)
    if trigger_id == 'add-user-button':
        if not current_user.is_authenticated or current_user.role not in ['admin', 'superadmin']:
            return validation_error("您没有执行此操作的权限。")
        # 安全输入校验
        # 基础空值检查
        if not username or not password:
            return validation_error("用户名和密码不能为空。")
        # 用户名校验 (6-20位，字母数字)
        if not (6 <= len(username) <= 20):
            return validation_error("用户名须由6-20个英文字母或数字组成，不得包含特殊字符。")
        # 禁止特殊字符 (只允许字母和数字)
        if not username.isalnum():
            return validation_error("用户名须由6-20个英文字母或数字组成，不得包含特殊字符。")
        # 密码校验 (8-30位，字母数字，含大小写和数字)
        if not (8 <= len(password) <= 30):
            return validation_error("密码须由8-30位大写字母、小写字母及数字组成，且不得包含特殊字符。")
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        if not (has_upper and has_lower and has_digit):
            return validation_error("密码须由8-30位大写字母、小写字母及数字组成，且不得包含特殊字符。")
        # 禁止特殊字符
        if not password.isalnum():
            return validation_error("密码须由8-30位大写字母、小写字母及数字组成，且不得包含特殊字符。")

        # 权限检查
        is_super_admin = current_user.role == 'superadmin'
        if role == 'superadmin':
            return validation_error("禁止通过此界面创建超级管理员账户。")
        if role == 'admin' and not is_super_admin:
            return validation_error("只有超级管理员才能创建新的管理员账户。")

        # 检查通过：暂存数据并弹出模态框
        store_data_new = {'username': username, 'password': password, 'role': role}
        modal_body = html.Div([html.P("请确认以下信息："), html.P([html.Strong("用户名: "), html.Span(username)]),
                               html.P([html.Strong("角色: "), html.Span(role.upper())]),
                               html.P(html.Strong("密码将以加密形式存储。"))])
        return True, modal_body, store_data_new, no_update, no_update, no_update, no_update

    # 3. 触发源：确认添加按钮 (执行操作)
    if trigger_id == 'confirm-add-user-button' and store_data:
        username, password, role = store_data.get('username'), store_data.get('password'), store_data.get('role')
        success, message = add_user(username, password, role)
        status = 'SUCCESS' if success else 'FAILURE'
        log_action(operator, action_type, username, status, message)

        if success:
            return False, no_update, None, dbc.Alert(message, color="success"), 0, *clear_inputs
        else:
            return False, no_update, None, dbc.Alert(message, color="danger"), no_update, no_update, no_update

    return no_update, no_update, no_update, no_update, no_update, no_update, no_update

@callback(
    Output('change-password-modal', 'is_open'),
    Output('change-pass-modal-title', 'children'),
    Output('change-password-user-store', 'data'),
    Output('table-operation-alert', 'children', allow_duplicate=True),
    Output("new-password-change-input", "value"),
    Output("confirm-password-change-input", "value"),
    Input('user-table', 'active_cell'), State('user-table', 'data'),
    prevent_initial_call=True
)
def trigger_change_password_modal(active_cell, table_data):
    if not active_cell or active_cell['column_id'] != 'change_pass' or not table_data:
        return no_update, no_update, no_update, no_update, no_update, no_update
    user_to_act = table_data[active_cell['row']]

    # 权限检查
    if not current_user.is_authenticated or current_user.role not in ['admin', 'superadmin']:
        return False, no_update, None, dbc.Alert("您没有执行此操作的权限。", color="danger"), no_update, no_update
    if user_to_act['username'] == current_user.username:
        return False, no_update, None, dbc.Alert("您不能在此处修改自己的密码，请使用个人设置。",
                                                 color="warning"), no_update, no_update
    is_super_admin_user = current_user.username == 'admin'
    target_role = user_to_act['role']
    if not is_super_admin_user and target_role in ['admin', 'superadmin']:
        return False, no_update, None, dbc.Alert(f"权限不足：您无权修改 {target_role} 账户的密码。",
                                                 color="danger"), no_update, no_update

    store_data = {'id': user_to_act['id'], 'username': user_to_act['username'], 'role': user_to_act['role']}
    return True, f"为用户 {user_to_act['username']} 修改密码", store_data, no_update, '', ''


@callback(
    # 第一次 Modal (输入密码)
    Output('change-pass-alert-inner', 'children'),
    Output('change-password-modal', 'is_open', allow_duplicate=True),
    Output("new-password-change-input", "value", allow_duplicate=True),
    Output("confirm-password-change-input", "value", allow_duplicate=True),
    # 第二次 Modal (二次确认)
    Output('change-pass-confirm-modal', 'is_open'),
    Output('change-pass-final-confirm-body', 'children'),
    # 存储新密码
    Output("new-password-temp-store", "data"),

    Input('confirm-password-change-button', 'n_clicks'),
    Input('cancel-password-change-button', 'n_clicks'),

    State('new-password-change-input', 'value'),
    State('confirm-password-change-input', 'value'),
    State('change-password-user-store', 'data'),
    prevent_initial_call=True
)
def handle_password_change_validation_and_confirm(confirm_n, cancel_n, new_password, confirm_password, user_store):
    ctx = dash.callback_context
    if not ctx.triggered or not user_store:
        # alert, modal_open, input1, input2, confirm_open, confirm_body, password_store
        return no_update, no_update, no_update, no_update, no_update, no_update, no_update

    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    clear_inputs = '', ''
    username = user_store.get('username')

    # 辅助函数：生成并返回错误警告
    def validation_error(message):
        # alert, modal_open, input1, input2, confirm_open, confirm_body, password_store
        return dbc.Alert(message, color="danger"), no_update, *clear_inputs, False, no_update, no_update

    # 1. 取消按钮 (关闭第一次 Modal)
    if trigger_id == 'cancel-password-change-button':
        # 清空密码输入，关闭第一次Modal
        return '', False, *clear_inputs, no_update, no_update, no_update

    # 2. “确认”按钮 (验证密码并弹出二次确认)
    if trigger_id == 'confirm-password-change-button':

        # --- 校验：空值检查 ---
        if not new_password or not confirm_password:
            return validation_error("新密码和确认密码都不能为空。")

        # --- 校验：两次输入是否一致 ---
        if new_password != confirm_password:
            return validation_error("两次输入的密码不一致，请重新输入。")

        # 密码校验 (8-30位)
        if not (8 <= len(new_password) <= 30):
            return validation_error("密码须由8-30位大写字母、小写字母及数字组成，且不得包含特殊字符。")

        # 密码强度校验 (含大小写和数字)
        has_upper = any(c.isupper() for c in new_password)
        has_lower = any(c.islower() for c in new_password)
        has_digit = any(c.isdigit() for c in new_password)

        if not (has_upper and has_lower and has_digit):
            return validation_error("密码须由8-30位大写字母、小写字母及数字组成，且不得包含特殊字符。")

        # 密码特殊字符校验 (只允许字母和数字)
        if not new_password.isalnum():
            return validation_error("密码须由8-30位大写字母、小写字母及数字组成，且不得包含特殊字符。")

        # 验证通过：
        # 1) 关闭第一个 Modal
        first_modal_open = False
        # 2) 暂存新密码
        password_temp_store = new_password
        # 3) 打开第二个 Modal (二次确认)
        second_modal_open = True
        confirm_body = html.P([
            "您确定要为用户 ", html.Strong(username), " 重置密码吗？",
            html.Br(),
            html.Strong("请确保您已记住新密码。", className='text-danger')
        ])

        # 返回: alert, modal_open, input1, input2, confirm_open, confirm_body, password_store
        return '', first_modal_open, *clear_inputs, second_modal_open, confirm_body, password_temp_store

    return no_update, no_update, no_update, no_update, no_update, no_update, no_update


@callback(
    # Outputs
    Output('change-pass-confirm-modal', 'is_open', allow_duplicate=True),
    Output('table-operation-alert', 'children', allow_duplicate=True),
    Output("users-interval", "n_intervals", allow_duplicate=True),
    Output("new-password-temp-store", "data", allow_duplicate=True),

    # Inputs
    Input('execute-password-change-button', 'n_clicks'),
    Input('cancel-final-password-change-button', 'n_clicks'),

    # States
    State('change-password-user-store', 'data'),
    State('new-password-temp-store', 'data'),
    prevent_initial_call=True
)
def handle_password_change_execution(execute_n, cancel_n, user_store, new_password):
    ctx = dash.callback_context
    if not ctx.triggered or not user_store:
        return no_update, no_update, no_update, no_update

    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    operator, action_type = current_user.username, 'UPDATE_PASSWORD'
    username, user_id = user_store.get('username'), user_store.get('id')

    # 1. 取消按钮 (关闭二次确认 Modal)
    if trigger_id == 'cancel-final-password-change-button':
        return False, no_update, no_update, None

    # 2. 确认执行按钮 (执行操作)
    if trigger_id == 'execute-password-change-button' and new_password:
        success, message = update_user_password(user_id, new_password)
        status = 'SUCCESS' if success else 'FAILURE'
        log_action(operator, action_type, username, status, message)

        # 清空暂存密码
        temp_store_data = None

        if success:
            alert = dbc.Alert(f"用户 {username} 的密码已成功修改。", color="success")
            return False, alert, 0, temp_store_data
        else:
            alert = dbc.Alert(f"密码修改失败: {message}", color="danger")
            return False, alert, no_update, temp_store_data

    return no_update, no_update, no_update, no_update


@callback(
    Output('delete-confirm-modal', 'is_open'),
    Output('delete-modal-body', 'children'),
    Output('delete-user-store', 'data'),
    Output('table-operation-alert', 'children', allow_duplicate=True),
    Output("users-interval", "n_intervals", allow_duplicate=True),

    Input('user-table', 'active_cell'),
    Input('confirm-delete-button', 'n_clicks'),
    Input('cancel-delete-button', 'n_clicks'),

    State('user-table', 'data'),
    State('delete-user-store', 'data'),
    prevent_initial_call=True
)
def handle_delete_operations(active_cell, confirm_n, cancel_n, table_data, store_data):
    ctx = dash.callback_context
    if not ctx.triggered: return no_update, no_update, no_update, no_update, no_update
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    operator, action_type = current_user.username, 'DELETE_USER'

    # 1. 表格点击 (打开 Modal)
    if trigger_id == 'user-table' and active_cell and active_cell['column_id'] == 'delete_btn':
        user_to_delete = table_data[active_cell['row']]

        if not current_user.is_authenticated or current_user.role not in ['admin', 'superadmin']:
            return False, no_update, no_update, dbc.Alert("您没有执行此操作的权限。", color="danger"), no_update
        if user_to_delete['username'] == current_user.username:
            return False, no_update, no_update, dbc.Alert("您不能删除自己的账户。", color="warning"), no_update

        target_role = user_to_delete.get('role', 'user')
        is_super_admin_user = current_user.username == 'admin'
        if not is_super_admin_user and target_role in ['admin', 'superadmin']:
            return False, no_update, no_update, dbc.Alert(f"权限不足：您无权删除 {target_role} 账户。",
                                                          color="danger"), no_update

        store_data_new = {'id': user_to_delete['id'], 'username': user_to_delete['username'], 'role': target_role}
        modal_body = html.P(["您确定要删除用户 ", html.Strong(user_to_delete['username']),
                             f" (角色: {target_role}) 吗？此操作不可撤销！"])
        return True, modal_body, store_data_new, no_update, no_update

    # 2. 确认删除按钮 (执行删除)
    elif trigger_id == 'confirm-delete-button' and store_data:
        row_id, username = store_data['id'], store_data['username']
        success, message = delete_user(row_id)
        status = 'SUCCESS' if success else 'FAILURE'
        log_action(operator, action_type, username, status, message)
        if success:
            return False, no_update, None, dbc.Alert(message, color="success"), 0
        else:
            return False, no_update, None, dbc.Alert(f"删除用户 {username} 失败: {message}。", color="danger"), no_update

    # 3. 取消按钮 (关闭 Modal)
    elif trigger_id == 'cancel-delete-button':
        return False, no_update, None, no_update, no_update

    return no_update, no_update, no_update, no_update, no_update