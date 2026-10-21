# db/db_pandas_query.py

import pandas as pd
import datetime
import pytz
# 导入连接函数
from db import get_sql_engine

# 历史数据读取

def get_historical_klines_data(symbol='BTCUSDT', interval='1d', start_date=None, end_date=None) -> pd.DataFrame:
    """获取指定时间段内的历史 K 线数据。"""
    engine = get_sql_engine()
    if not engine: return pd.DataFrame()
    try:
        query = "SELECT open_time, close_time, open, high, low, close, volume FROM klines_data"
        conditions = ["symbol = %s", "`interval` = %s"]
        params = [symbol, interval]

        if start_date and end_date:
            conditions.append("close_time BETWEEN %s AND %s")
            params.extend([start_date, end_date])

        query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY close_time ASC"

        df = pd.read_sql_query(query, engine, params=tuple(params))

        if not df.empty:
            df['open_time'] = pd.to_datetime(df['open_time']).dt.tz_localize(pytz.utc)
            df['close_time'] = pd.to_datetime(df['close_time']).dt.tz_localize(pytz.utc)
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    except Exception as err:
        print(f"[DB_PANDAS_ERROR] 读取历史数据失败: {err}")
        return pd.DataFrame()


def _get_raw_klines_for_prediction(symbol='BTCUSDT', interval='1d') -> pd.DataFrame:
    """内部函数：从数据库获取预测模型所需的基础 K 线数据。"""
    engine = get_sql_engine()
    if engine is None:
        print("无法建立数据库连接，预测模型无法获取 K 线数据。")
        return pd.DataFrame(columns=['close_time', 'open', 'high', 'low', 'close', 'volume'])
    try:
        query = """
        SELECT close_time, open, high, low, close, volume
        FROM klines_data
        WHERE symbol = %s AND `interval` = %s
        ORDER BY close_time ASC
        """
        params = [symbol, interval]

        df = pd.read_sql_query(query, engine, params=tuple(params))

        if not df.empty:
            df['close_time'] = pd.to_datetime(df['close_time']).dt.tz_localize(pytz.utc)
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    except Exception as err:
        print(f"[DB_PANDAS_ERROR] 读取预测模型历史 K 线数据失败: {err}")
        return pd.DataFrame(columns=['close_time', 'open', 'high', 'low', 'close', 'volume'])


def get_historical_fgi_data() -> pd.DataFrame:
    """从数据库读取所有 FGI 历史数据，并返回以日期为索引的 DataFrame。"""
    engine = get_sql_engine()
    if not engine: return pd.DataFrame()
    try:
        query = """
        SELECT close_date, fgi_value AS FGI
        FROM fgi_data
        ORDER BY close_date ASC
        """
        df = pd.read_sql_query(query, engine, index_col='close_date')

        if not df.empty:
            index = pd.to_datetime(df.index).tz_localize(pytz.utc).normalize()
            df.index = index
            df.index.name = 'close_time'
            df['FGI'] = pd.to_numeric(df['FGI'], errors='coerce')
        return df
    except Exception as err:
        print(f"[DB_PANDAS_ERROR] 从数据库读取 FGI 数据失败: {err}")
        return pd.DataFrame()


# 展示查询

def get_latest_klines_df(symbol='BTCUSDT', interval='1d') -> pd.DataFrame:
    """获取所有符合条件的 K 线数据，用于后台 DataTable 展示。"""
    engine = get_sql_engine()
    if not engine: return pd.DataFrame()
    try:
        query = """
            SELECT close_time, open, high, low, close, volume
            FROM klines_data
            WHERE symbol = %s AND `interval` = %s
            ORDER BY close_time DESC
        """
        params = [symbol, interval]
        df = pd.read_sql_query(query, engine, params=tuple(params))

        if not df.empty:
            df['close_time'] = pd.to_datetime(df['close_time']).dt.strftime('%Y-%m-%d %H:%M:%S')
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce').round(4)

        df.columns = ['收盘时间', '开盘价', '最高价', '最低价', '收盘价', '成交量']
        return df
    except Exception as err:
        print(f"[DB_PANDAS_ERROR] 读取 K 线数据失败: {err}")
        return pd.DataFrame()


def get_predictions_data_from_db() -> pd.DataFrame:
    """从数据库读取所有预测数据。"""
    engine = get_sql_engine()
    if not engine: return pd.DataFrame()
    try:
        query = "SELECT * FROM future_predictions ORDER BY close_time ASC"
        df = pd.read_sql(query, engine)
        if not df.empty:
            df['close_time'] = pd.to_datetime(df['close_time'])
        return df
    except Exception as err:
        print(f"[DB_PANDAS_ERROR] 从数据库读取预测数据失败: {err}")
        return pd.DataFrame()


def get_latest_predictions_df(symbol='BTCUSDT') -> pd.DataFrame:
    """获取所有预测数据，用于后台 DataTable 展示。"""
    engine = get_sql_engine()
    if not engine: return pd.DataFrame()
    try:
        query = """
            SELECT close_time, predicted_price, prediction_time
            FROM future_predictions
            ORDER BY close_time DESC
        """
        df = pd.read_sql_query(query, engine)

        if not df.empty:
            df['close_time'] = pd.to_datetime(df['close_time']).dt.strftime('%Y-%m-%d %H:%M:%S')
            df['prediction_time'] = pd.to_datetime(df['prediction_time']).dt.strftime('%Y-%m-%d %H:%M:%S')
            df['predicted_price'] = pd.to_numeric(df['predicted_price'], errors='coerce').round(4)
            df.columns = ['目标时间', '预测价格', '预测生成时间']

        return df
    except Exception as err:
        print(f"[DB_PANDAS_ERROR] 读取预测数据失败: {err}")
        return pd.DataFrame()


def get_latest_realtime_ticker_df() -> pd.DataFrame:
    """获取 realtime_ticker 表中的所有最新数据，并以 DataFrame 格式返回。"""
    engine = get_sql_engine()
    if not engine: return pd.DataFrame()
    try:
        query = """
            SELECT symbol, lastPrice, priceChangePercent, highPrice, lowPrice, openPrice, volume, fetch_time
            FROM realtime_ticker
            ORDER BY fetch_time DESC
        """
        df = pd.read_sql_query(query, engine)

        if not df.empty:
            df['fetch_time'] = df['fetch_time'].dt.strftime('%Y-%m-%d %H:%M:%S')
            cols_to_round = ['lastPrice', 'highPrice', 'lowPrice', 'openPrice', 'volume']
            for col in cols_to_round:
                df[col] = pd.to_numeric(df[col], errors='coerce').round(4)
            df['priceChangePercent'] = pd.to_numeric(df['priceChangePercent'], errors='coerce').round(2)

            df.columns = ['交易对', '最新价', '涨跌幅(%)', '最高价', '最低价', '开盘价', '成交量', '采集时间(UTC)']

        return df
    except Exception as err:
        print(f"[DB_PANDAS_ERROR] 读取最新实时数据失败: {err}")
        return pd.DataFrame()


# 日志查询/写入

def get_status_code_summary(limit=10) -> pd.DataFrame:
    """从 server_logs 表中查询状态码的出现次数。"""
    engine = get_sql_engine()
    if not engine: return pd.DataFrame()

    try:
        sql_base_query = """
        SELECT status_code, COUNT(status_code) AS count FROM server_logs
        WHERE status_code IS NOT NULL
        GROUP BY status_code
        ORDER BY count DESC
        """
        limit_clause = f"LIMIT {limit}" if limit is not None else ""
        sql_query = f"{sql_base_query} {limit_clause};"

        df = pd.read_sql_query(sql_query, engine)

        if not df.empty:
            df['status_code'] = pd.to_numeric(df['status_code'], errors='coerce').astype('Int64')
            df['count'] = df['count'].astype(int)

        return df
    except Exception as e:
        print(f"[DB_PANDAS_ERROR] Error in get_status_code_summary: {e}")
        return pd.DataFrame()


def get_audit_logs() -> pd.DataFrame:
    """从 user_logs 表中获取所有操作日志。"""
    engine = get_sql_engine()
    if not engine: return pd.DataFrame()
    try:
        query = "SELECT timestamp, operator, action_type, target_user, status, message FROM user_logs ORDER BY timestamp DESC"
        df = pd.read_sql_query(query, engine)
        return df
    except Exception as e:
        print(f"[DB_PANDAS_ERROR] 获取审计日志失败: {e}")
        return pd.DataFrame()


def log_user_action(operator, action_type, status, message=None, target_user=None):
    """记录用户操作到 user_logs 表 (使用 df.to_sql)。"""
    engine = get_sql_engine()
    if not engine:
        print("无法获取 SQL Engine，无法记录用户操作日志。")
        return

    timestamp = datetime.datetime.now()
    target = target_user if target_user else operator

    log_data = {
        'timestamp': timestamp,
        'operator': operator,
        'action_type': action_type,
        'target_user': target,
        'status': status,
        'message': message
    }

    df_log = pd.DataFrame([log_data])

    try:
        df_log.to_sql(name='user_logs', con=engine, if_exists='append', index=False)
        print(f"[LOG_ACTION SUCCESS] {action_type} by {operator} ({status}): {message}")

    except Exception as e:
        print(f"[DB_PANDAS_ERROR] Error logging action to DB using to_sql: {e}")