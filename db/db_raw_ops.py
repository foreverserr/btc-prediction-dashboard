# db/db_raw_ops.py

import pandas as pd
import mysql.connector
import datetime
import pytz
# 导入连接函数
from .db_connect import get_conn_from_pool


# 基础状态检查

def is_db_empty(symbol='BTCUSDT', interval='1d') -> bool:
    """检查数据库中某个 K 线是否存在数据。"""
    conn = get_conn_from_pool()
    if not conn: return True
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM klines_data WHERE symbol = %s AND `interval` = %s", (symbol, interval))
        result = cursor.fetchone()
        return result[0] == 0
    except mysql.connector.Error as err:
        print(f"[DB_RAW_ERROR] 检查数据库是否为空时出错: {err}")
        return True
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()


# 核心数据 UPSERT

def insert_klines_data(df, symbol, interval):
    """插入或更新 K 线数据 (使用 ON DUPLICATE KEY UPDATE)。"""
    conn = get_conn_from_pool()
    if not conn: return
    cursor = None
    try:
        cursor = conn.cursor()
        records = [
            (symbol, interval, row['open_time'], row['close_time'], row['open'], row['high'], row['low'], row['close'],
             row['volume'])
            for _, row in df.iterrows()
        ]
        insert_query = """
            INSERT INTO klines_data (symbol, `interval`, open_time, close_time, open, high, low, close, volume)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            open_time = VALUES(open_time), close_time = VALUES(close_time), open = VALUES(open), high = VALUES(high), 
            low = VALUES(low), close = VALUES(close), volume = VALUES(volume), update_time = CURRENT_TIMESTAMP
        """
        cursor.executemany(insert_query, records)
        conn.commit()
    except mysql.connector.Error as err:
        print(f"[DB_RAW_ERROR] K线数据插入失败: {err}")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()


def upsert_fgi_data(df: pd.DataFrame):
    """插入或更新 FGI 数据到 fgi_data 表 (使用 ON DUPLICATE KEY UPDATE)。"""
    if df.empty or 'FGI' not in df.columns:
        print("FGI DataFrame 为空或缺少 'FGI' 列，跳过写入。")
        return

    conn = get_conn_from_pool()
    if not conn: return

    cursor = None
    try:
        cursor = conn.cursor()

        fgi_df = df[['FGI']].copy()
        fgi_df.reset_index(inplace=True)
        fgi_df.rename(columns={'close_time': 'close_date', 'FGI': 'fgi_value'}, inplace=True)

        records = [
            (row['close_date'].date(), int(row['fgi_value']))
            for _, row in fgi_df.iterrows()
        ]

        insert_query = """
            INSERT INTO fgi_data (close_date, fgi_value)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE 
            fgi_value = VALUES(fgi_value), update_time = CURRENT_TIMESTAMP
        """

        cursor.executemany(insert_query, records)
        conn.commit()


    except mysql.connector.Error as err:
        print(f"[DB_RAW_ERROR] FGI 数据插入失败: {err}")
        if conn: conn.rollback()
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()


def upsert_realtime_ticker(data: dict):
    """插入或更新实时行情数据 (需要原生事务)。"""
    conn = get_conn_from_pool()
    if not conn:
        print("无法建立数据库连接，跳过写入。")
        return
    cursor = None
    try:
        cursor = conn.cursor()
        query = """
        INSERT INTO realtime_ticker (symbol, lastPrice, priceChangePercent, highPrice, lowPrice, openPrice, volume, fetch_time) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE 
            lastPrice=VALUES(lastPrice), priceChangePercent=VALUES(priceChangePercent), 
            highPrice=VALUES(highPrice), lowPrice=VALUES(lowPrice), openPrice=VALUES(openPrice), volume=VALUES(volume), fetch_time=VALUES(fetch_time)
        """
        cursor.execute(query, (
            data.get('symbol'),
            float(data.get('lastPrice')),
            float(data.get('priceChangePercent')),
            float(data.get('highPrice')),
            float(data.get('lowPrice')),
            float(data.get('openPrice')),
            float(data.get('volume')),
            datetime.datetime.now()
        ))
        conn.commit()
    except mysql.connector.Error as err:
        print(f"[DB_RAW_ERROR] 插入实时数据时出错: {err}")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()


# 实时/最新时间戳获取

def get_latest_klines_timestamp(symbol='BTCUSDT', interval='1d') -> int or None:
    """获取最新的 K 线 close_time 时间戳 (毫秒)。"""
    conn = get_conn_from_pool()
    if not conn: return None
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(close_time) FROM klines_data WHERE symbol = %s AND `interval` = %s",
                       (symbol, interval))
        result = cursor.fetchone()
        if result and result[0]:
            return int(result[0].timestamp() * 1000)
    except mysql.connector.Error as err:
        print(f"[DB_RAW_ERROR] 获取最新时间戳失败: {err}")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()
    return None


def get_latest_fgi_timestamp() -> datetime.date or None:
    """从数据库中获取最新的 FGI close_date (datetime.date 对象)。"""
    conn = get_conn_from_pool()
    if not conn: return None
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(close_date) FROM fgi_data")
        result = cursor.fetchone()
        if result and result[0]:
            return result[0]
        return None
    except mysql.connector.Error as err:
        print(f"[DB_RAW_ERROR] 获取最新 FGI 时间戳失败: {err}")
        return None
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()


def get_latest_complete_klines_timestamp(symbol='BTCUSDT', interval='1d') -> int or None:
    """获取最新完整 K 线时间戳 (排除当日未完成的 K 线)。"""
    conn = get_conn_from_pool()
    if not conn: return None
    cursor = None
    latest_ts = None
    try:
        cursor = conn.cursor()
        yesterday_end_utc = datetime.datetime.now(pytz.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        query = """
            SELECT MAX(close_time) FROM klines_data 
            WHERE symbol = %s AND `interval` = %s AND close_time < %s
        """
        cursor.execute(query, (symbol, interval, yesterday_end_utc))
        result = cursor.fetchone()
        if result and result[0]:
            latest_ts = int(result[0].timestamp() * 1000)
    except mysql.connector.Error as err:
        print(f"[DB_RAW_ERROR] 获取最新完整时间戳失败: {err}")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()
    return latest_ts


def get_latest_realtime_ticker(symbol='BTCUSDT') -> dict or None:
    """获取最新的实时行情数据并进行类型转换 (需要原生游标)。"""
    conn = get_conn_from_pool()
    if not conn: return None
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM realtime_ticker WHERE symbol = %s"
        cursor.execute(query, (symbol,))
        result = cursor.fetchone()
        if result:
            for key in ['lastPrice', 'priceChangePercent', 'highPrice', 'lowPrice', 'openPrice', 'volume']:
                result[key] = float(result[key]) if result[key] is not None else 0.0
        return result
    except mysql.connector.Error as err:
        print(f"[DB_RAW_ERROR] 读取实时数据时出错: {err}")
        return None
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()


def get_latest_realtime_ticker_for_admin(symbol='BTCUSDT'):
    """用于 Admin 页面，获取最新的实时行情数据并格式化。（调用原生读取函数）"""
    raw_data = get_latest_realtime_ticker(symbol)
    if not raw_data:
        return None

    fetch_time = raw_data.get('fetch_time')
    if fetch_time and fetch_time.tzinfo is None:
        fetch_time = pytz.utc.localize(fetch_time)

    timestamp_local = fetch_time.astimezone(pytz.timezone('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S')

    return {
        'ticker': raw_data.get('symbol', 'N/A'),
        'lastPrice': raw_data.get('lastPrice', 0.0),
        'timestamp': timestamp_local
    }


def get_klines_summary(symbol='BTCUSDT', interval='1d'):
    """用于 Admin 页面，获取 klines_data 表的摘要信息。（使用原生连接）"""
    conn = get_conn_from_pool()
    if not conn:
        return None
    cursor = None
    summary = {'count': 0, 'first_time': 'N/A', 'last_time': 'N/A'}
    try:
        cursor = conn.cursor()
        # 1. 获取总行数
        cursor.execute("SELECT COUNT(*) FROM klines_data WHERE symbol = %s AND `interval` = %s", (symbol, interval))
        summary['count'] = cursor.fetchone()[0]

        if summary['count'] > 0:
            # 2. 获取最早的时间
            cursor.execute("""
                SELECT MIN(close_time) FROM klines_data 
                WHERE symbol = %s AND `interval` = %s
            """, (symbol, interval))
            first_time_utc = cursor.fetchone()[0]
            summary['first_time'] = first_time_utc.strftime('%Y-%m-%d %H:%M:%S UTC') if first_time_utc else 'N/A'

            # 3. 获取最晚的时间
            cursor.execute("""
                SELECT MAX(close_time) FROM klines_data 
                WHERE symbol = %s AND `interval` = %s
            """, (symbol, interval))
            last_time_utc = cursor.fetchone()[0]
            summary['last_time'] = last_time_utc.strftime('%Y-%m-%d %H:%M:%S UTC') if last_time_utc else 'N/A'

        return summary
    except mysql.connector.Error as err:
        print(f"[DB_RAW_ERROR] 获取 K 线数据摘要失败: {err}")
        return None
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

def get_last_prediction_close_time():
    """
    从 future_predictions 表中获取上次预测的 K 线基准时间 (close_time)。
    这个时间是上次预测时使用的最后一条历史 K 线的时间。
    """
    conn = get_conn_from_pool()
    if not conn:
        return None
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        # 查找表中 'close_time' 最早的一行，它对应于我们存入的最后一天历史数据作为基准点
        # 如果表是空的，结果是 None
        query = "SELECT close_time FROM future_predictions ORDER BY close_time ASC LIMIT 1"
        cursor.execute(query)
        result = cursor.fetchone()

        if result and result['close_time']:
            # 返回 datetime.datetime 对象
            return result['close_time']
        return None
    except Exception as e:
        # 如果表不存在或读取失败，返回 None，程序将继续运行预测
        print(f"读取上次预测时间失败: {e}")
        return None
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()