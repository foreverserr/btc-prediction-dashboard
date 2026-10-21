# db/__init__.py

# 导入必要的模块
from .db_connect import (
    connect_db, get_conn_from_pool, init_db, get_sql_engine
)

# 假设您的用户管理模块 (user_manager.py) 结构保持不变
# 导入用户管理模块的函数
from .user_manager import (
    User, get_user_by_username, get_user_by_id, verify_password,
    add_user, delete_user, get_all_users, update_user_password,
    log_action, get_user_session_token, update_user_session_token
)

# 导入日志处理模块的函数 (log_handler.py)
from .log_handler import (
    DBLogHandler, setup_log_handlers
)

# 导入 db_raw_ops.py 中的函数 (原生 SQL / 事务 / 单值读取)
from .db_raw_ops import (
    is_db_empty,
    insert_klines_data,
    upsert_fgi_data,
    upsert_realtime_ticker,
    get_latest_klines_timestamp,
    get_latest_fgi_timestamp,
    get_latest_complete_klines_timestamp,
    get_latest_realtime_ticker,
    get_latest_realtime_ticker_for_admin,
    get_klines_summary,
    get_last_prediction_close_time,
)

# 导入 db_pandas_query.py 中的函数 (Pandas / SQLAlchemy 查询)
from .db_pandas_query import (
    get_historical_klines_data,
    get_historical_fgi_data,
    get_latest_klines_df,
    get_predictions_data_from_db,
    get_latest_predictions_df,
    get_latest_realtime_ticker_df,
    get_status_code_summary,
    get_audit_logs,
    log_user_action,
)

# --- 导入 db_prediction_ops.py 中的函数 (预测数据 ETL/存储) ---
from .db_prediction_ops import (
    get_fgi_data_for_merge,
    get_prediction_klines_data,
    save_predictions_to_db,
)