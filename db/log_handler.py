import logging
import re
from datetime import datetime
from db import get_conn_from_pool
try:
    import dash
    from dash import page_registry
except ImportError:
    page_registry = {'values': []}  # 提供一个包含 'values' 键的结构，防止后续代码报错

# 定义一个全局的 ANSI 颜色代码清理正则
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

# ⭐ 核心修改 1: 增强忽略的路径模式列表
IGNORE_PATH_PATTERNS = [
    '/_dash-',  # Dash 内部 API 调用，如 /_dash-update-component
    '/assets/',  # 静态资源，如 CSS, JS, 图片
    '/favicon.ico',  # 浏览器图标请求 (无下划线)
    '/_favicon.ico'  # 浏览器图标请求 (带下划线)
]


class DBLogHandler(logging.Handler):
    """一个将日志记录发送到 MySQL 数据库的自定义日志处理器。"""

    def __init__(self, table_name='server_logs'):
        super().__init__()
        self.table_name = table_name

        # 鲁棒的正则表达式，用于捕获所有状态码日志行
        self.request_log_pattern = re.compile(
            r'^(?P<ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) - - \[(?P<time>[^\]]+)\] "(?P<method>[A-Z]+) (?P<path>[^\s]+) [^\s]+" (?P<status>\d{3}).*$'
        )

    def clean_ansi(self, text):
        """去除字符串中的 ANSI 颜色转义序列。"""
        return ANSI_ESCAPE.sub('', text)

    def emit(self, record):
        """处理一条日志记录并将其写入数据库。"""
        conn = None
        cursor = None

        # 1. 准备日志数据
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        level = record.levelname
        module = record.name
        message = self.clean_ansi(self.format(record))

        ip_address = None
        request_path = None
        status_code = None

        # 2. 尝试解析 Web 请求日志 (来自 'werkzeug' 模块)
        is_werkzeug_request = (module == 'werkzeug' and ('GET' in message or 'POST' in message))

        if is_werkzeug_request:
            match = self.request_log_pattern.search(message)
            if match:
                data = match.groupdict()
                ip_address = data.get('ip')

                # 提取完整路径，并去除查询参数
                full_request_path = data.get('path')
                request_path = full_request_path.split('?')[0] if full_request_path else None
                status_code = int(data.get('status')) if data.get('status') else None

            # 忽略内部路径
            if request_path:
                for pattern in IGNORE_PATH_PATTERNS:
                    # 使用 starts with 匹配前缀
                    if request_path.startswith(pattern):
                        # 如果匹配到忽略模式，立即返回，不写入数据库
                        return

                # 将未注册的 200 请求在数据库中标记为 404
                if status_code == 200:
                    # 获取已注册的 Dash 路由列表
                    # 必须使用 page_registry.values()
                    registered_paths = [page['path'] for page in page_registry.values()]

                    # 如果状态码是 200，且路径未在注册列表中
                    if request_path not in registered_paths:
                        # 仅在非根路径且未注册时，标记为 404
                        # (假设 '/' 是登录页或其他处理逻辑)
                        if request_path != '/':
                            status_code = 404
                            # 提升日志级别以突出显示这条伪 404 记录
                            level = 'WARNING'
                            # 在 message 中添加标记，便于在数据库中识别
                            message = message + ' (Logged as 404: Unregistered SPA Path)'

            # 3. 针对非 werkzeug 模块（如 root logger 记录的 404/500 错误）
        # 如果不是 werkzeug 请求，但级别低于 WARNING，则可能也不需要记录 (例如 root logger 的 DEBUG/INFO)
        if not is_werkzeug_request and level not in ['WARNING', 'ERROR', 'CRITICAL']:
            # 假设您只希望 root logger 记录 WARNING 及以上的自定义消息
            return

        # 4. 数据库写入
        try:
            conn = get_conn_from_pool()
            if not conn:
                return

            cursor = conn.cursor()

            insert_sql = f"""
                INSERT INTO server_logs 
                (timestamp, level, module, message, ip_address, request_path, status_code)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            log_data = (
                timestamp,
                level,
                module,
                message,
                ip_address,
                request_path,
                status_code
            )

            cursor.execute(insert_sql, log_data)
            conn.commit()

        except Exception as e:
            # 打印错误，但确保不中断主应用
            print(f"写入数据库日志时发生错误: {e}")

        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()


def setup_log_handlers():
    """设置所有日志处理器（werkzeug, pandas, root）"""

    print("正在设置日志处理器...")
    db_handler = DBLogHandler()
    db_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(message)s')
    db_handler.setFormatter(formatter)

    # 1. 捕捉 Web 请求日志 (来自 werkzeug 模块)
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.DEBUG)
    werkzeug_logger.addHandler(db_handler)

    # 2. 捕捉 Pandas 警告日志
    pandas_logger = logging.getLogger('pandas')
    pandas_logger.setLevel(logging.WARNING)
    pandas_logger.addHandler(db_handler)

    # 3. 捕捉根日志记录器的 WARNING 及以上日志
    root_logger = logging.getLogger()
    db_handler_for_root = DBLogHandler()
    db_handler_for_root.setLevel(logging.WARNING)
    db_handler_for_root.setFormatter(formatter)
    root_logger.addHandler(db_handler_for_root)

    print("数据库日志处理器配置完成。")