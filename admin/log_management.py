import dash_bootstrap_components as dbc
from dash import dcc, html, callback, Input, Output, State, dash_table, no_update
# 新增导入 Plotly Express
import plotly.express as px
# 核心导入：引入 current_user
from flask_login import current_user, AnonymousUserMixin

# 假设您已在 db.py 中实现这些函数
from db import get_status_code_summary
from db import get_audit_logs


# -----------------------------------------------------------------
# 1. 布局定义 (只返回一个占位符 Div)
# -----------------------------------------------------------------

def create_log_management_layout():
    """
    创建系统日志统计区域的布局占位符。
    实际的内容渲染将由回调函数负责，实现权限控制。
    """
    # 返回一个占位符 Div，由后面的回调填充内容
    return html.Div(id='log-management-section-container', children=[
        # 必须包含这个 dcc.Location，以便我们能通过监听它的 pathname 来触发权限检查
        dcc.Location(id='log-management-url', refresh=False),
        html.Div(id='log-management-content')  # 实际内容的容器
    ])


# -----------------------------------------------------------------
# 2. 核心权限检查与内容渲染回调 (延迟渲染)
# -----------------------------------------------------------------
@callback(
    # 输出到内容容器
    Output('log-management-content', 'children'),
    # 监听 dcc.Location 的 pathname，确保在页面加载和URL改变时触发
    Input('log-management-url', 'pathname')
)
def render_log_management_content(pathname):
    """
    在 Dash 运行时检查 current_user 状态，并根据权限动态渲染内容。
    """
    # 1. 核心权限检查：在安全的运行时环境中访问 current_user
    is_authenticated = getattr(current_user, 'is_authenticated', False)
    user_role = getattr(current_user, 'role', 'guest')

    # 2. 增强容错性：对角色进行清理和标准化 (去除空格，转小写)
    normalized_role = str(user_role).strip().lower()

    # 判断是否为 'superadmin'
    can_view_logs = is_authenticated and (normalized_role == 'superadmin')

    # 如果不满足权限 (即不是 superadmin)，返回一个不显示的空 Div
    if not can_view_logs:
        # 返回空 Div，实现彻底隐藏
        return html.Div(style={'display': 'none'})

    # ---------------------------------------------------
    # 如果是超级管理员，则渲染整个日志模块
    # ---------------------------------------------------

    log_management_content = dbc.Card(
        [
            dbc.CardHeader(
                html.H4("系统日志与监控", className="text-center fw-bold text-dark"),
                className="bg-light"
            ),
            dbc.CardBody(
                dbc.Row([
                    # 1. 状态码统计排行榜容器
                    dbc.Col(
                        dbc.Card([
                            # 标题不变，但内容将改为图表
                            dbc.CardHeader(html.H5("网页状态码统计图", className="text-center fw-bold")),
                            dbc.CardBody([
                                # 容器用于 dcc.Graph
                                html.Div(id="log-status-code-chart-container"),
                                dcc.Interval(id="log-stats-interval", interval=15000, disabled=False)
                            ])
                        ], className="shadow-lg h-100 border-warning"), lg=6, className="mb-4"
                    ),
                    # 2. 用户操作审计日志 (已内联，更简洁)
                    dbc.Col(
                        dbc.Card([
                            dbc.CardHeader(
                                html.H5("用户操作日志表", className="text-center fw-bold")),
                            dbc.CardBody([
                                html.Div(id="audit-log-table-container"),
                                # 定时器：直接启用 (disabled=False)
                                dcc.Interval(id="audit-log-interval", interval=30000, disabled=False)
                            ])
                        ], className="shadow-lg h-100 border-danger"), lg=6, className="mb-4"
                    )
                ],
                # 保持 Flexbox 以确保对齐，同时调整图表高度来匹配表格
                className="g-4 d-flex align-items-stretch"),
                className="p-4"
            ),
        ],
        className="mb-4 shadow-lg border-light bg-light text-dark",
        id='log-management-section-actual'
    )
    return log_management_content


# -----------------------------------------------------------------
# 3. 状态码统计回调 (图表高度调整为 400px)
# -----------------------------------------------------------------
@callback(
    # 输出 ID 已修改为 chart-container
    Output("log-status-code-chart-container", "children"),
    Input("log-stats-interval", "n_intervals")
)
def update_log_stats_chart(n):
    """获取并展示日志状态码统计扇形图，优化视觉和互动性。"""
    if not current_user.is_authenticated:
        return dbc.Alert("请登录以查看数据。", color="warning")

    try:
        df_stats = get_status_code_summary(limit=None)

        df_stats.columns = [col.lower() for col in df_stats.columns]

        if 'count' not in df_stats.columns or 'status_code' not in df_stats.columns or df_stats.empty:
            return dbc.Alert("日志统计数据结构错误或数据为空。", color="info")

        total_count = df_stats['count'].sum()
        if total_count == 0:
            return dbc.Alert("日志总访问次数为零。", color="info")

        # --- Plotly 图表生成逻辑 ---

        # 1. 对状态码进行分类 (2xx, 3xx, 4xx, 5xx)
        def categorize_status(code):
            try:
                code_str = str(int(code))
                if code_str.startswith('2'): return '2xx Success (成功)'
                if code_str.startswith('3'): return '3xx Redirection (重定向)'
                if code_str.startswith('4'): return '4xx Client Error (客户端错误)'
                if code_str.startswith('5'): return '5xx Server Error (服务器错误)'
                return 'Other (其他)'
            except:
                return 'Invalid (无效)'

        df_stats['Category'] = df_stats['status_code'].apply(categorize_status)

        # 2. 按类别聚合计数
        df_summary = df_stats.groupby('Category', as_index=False)['count'].sum()

        # 3. 定义颜色映射 (使用 Bootstrap 颜色进行区分)
        color_map = {
            '2xx Success (成功)': '#198754',  # Success (绿色)
            '3xx Redirection (重定向)': '#ffc107',  # Warning (黄色)
            '4xx Client Error (客户端错误)': '#dc3545',  # Danger (红色)
            '5xx Server Error (服务器错误)': '#6f42c1',  # Purple (自定义)
            'Other (其他)': '#6c757d',
            'Invalid (无效)': '#0dcaf0',
        }

        # 4. 创建扇形图
        fig = px.pie(
            df_summary,
            names='Category',
            values='count',
            color='Category',
            color_discrete_map=color_map,
            hole=.3  # 环形图效果
        )

        background_color = '#e8f0f5'  # 对应表格数据行的背景色
        text_color = '#1f2d3a'  # 字体颜色

        # 优化 Layout (布局)
        fig.update_layout(
            paper_bgcolor=background_color,
            plot_bgcolor=background_color,
            font_color=text_color,
            margin=dict(t=30, b=30, l=10, r=10),
            legend_title_text='状态类别',
            height=400,
            legend=dict(font=dict(size=10, color=text_color))
        )

        # 优化 Traces (数据轨迹/扇形区)
        fig.update_traces(
            hovertemplate="<b>%{label}</b><br>次数: %{value}<br>占比: %{percent}<extra></extra>",
            textinfo='percent',
            textposition='outside',  # 标签置于外部
            insidetextorientation='radial',
            marker=dict(line=dict(color=background_color, width=1)),
            textfont_color=text_color
        )

        # 6. 返回 dcc.Graph 组件
        # 允许工具栏显示，但可以禁用一些不常用的按钮，提升互动性
        config = {
            'displayModeBar': True,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d']
        }
        return dcc.Graph(figure=fig, config=config)

    except Exception as e:
        print(f"Error generating log stats chart: {e}")
        return dbc.Alert(f"加载日志统计图表失败，请检查后端日志和数据。", color="danger")


# -----------------------------------------------------------------
# 4. 用户审计日志回调 (表格分页改为 10)
# -----------------------------------------------------------------
@callback(
    Output("audit-log-table-container", "children"),
    Input("audit-log-interval", "n_intervals")
)
def update_audit_log_table(n):
    """
    获取并展示用户操作审计日志。
    """
    # 安全性检查：只允许 superadmin 看到审计日志数据
    user_role_check = getattr(current_user, 'role', 'guest').strip().lower()

    if not current_user.is_authenticated or user_role_check != 'superadmin':
        # 只有 superadmin 才能看到这个内容，这里是双重保险
        return dbc.Alert(
            "权限限制：用户操作审计日志仅对超级管理员开放。",
            color="danger",
            className="text-center"
        )

    try:
        df_logs = get_audit_logs()

        # ... (数据处理逻辑，保持不变) ...
        if df_logs.empty:
            return dbc.Alert("没有找到任何用户操作审计记录。", color="info")

        df_logs.columns = [col.lower() for col in df_logs.columns]

        # 确保列顺序和名称正确
        df_logs = df_logs[['timestamp', 'operator', 'action_type', 'target_user', 'status', 'message']]
        df_logs.columns = ['时间戳', '操作者', '操作类型', '目标用户', '状态', '消息']

        def get_status_style(status):
            status = str(status).upper()
            if status == 'SUCCESS':
                return {'color': '#1f2d3a', 'backgroundColor': '#198754'}  # success
            elif status == 'FAILURE':
                return {'color': '#1f2d3a', 'backgroundColor': '#dc3545'}  # danger
            else:
                return {'color': '#1f2d3a', 'backgroundColor': '#6c757d'}  # secondary

        data = df_logs.to_dict('records')
        style_data_conditional = [
            {
                'if': {'column_id': '状态',
                       'filter_query': '{状态} = "SUCCESS"'},
                'style': get_status_style('SUCCESS')
            },
            {
                'if': {'column_id': '状态',
                       'filter_query': '{状态} = "FAILURE"'},
                'style': get_status_style('FAILURE')
            }
        ]

        table = dash_table.DataTable(
            id='audit-log-table',
            columns=[{"name": i, "id": i} for i in df_logs.columns],
            data=data,
            page_action='native',
            page_size=10,
            style_header={
                'backgroundColor': '#cfdde6',
                'fontWeight': 'bold',
                'color': '#0f2f3f'
            },

            style_data={
                'backgroundColor': '#e8f0f5',
                'color': '#1f2d3a',
                'border': '1px solid #c8d6e2'
            },
            style_cell={
                'textAlign': 'center',
                'fontFamily': 'sans-serif',
                'fontSize': '11px',
                'minWidth': '50px',
                'maxWidth': '180px',
                'whiteSpace': 'normal'
            },
            style_data_conditional=style_data_conditional,
            # 保持 maxHeight，但 10 行时可能不需要
            style_table={'overflowY': 'auto', 'maxHeight': '350px'}
        )
        return table

    except Exception as e:
        print(f"Error fetching audit log data: {e}")
        return dbc.Alert(f"加载审计日志失败，请检查后端数据库连接和 'user_logs' 表结构。", color="danger")