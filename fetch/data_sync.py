# fetch/data_sync.py

import datetime
import time
import pytz
import pandas as pd

# 导入数据库操作函数
from db import (
    init_db, insert_klines_data, upsert_realtime_ticker, get_latest_realtime_ticker,
    get_latest_complete_klines_timestamp, is_db_empty, upsert_fgi_data, get_latest_fgi_timestamp
)
# 导入 API 客户端
from .binance_api import fetch_binance_klines, fetch_binance_ticker
from .fgi_data import get_historical_fear_and_greed_data # 必须直接导入 FGI 函数，以避免循环导入


def sync_realtime_ticker(symbol='BTCUSDT'):
    """
    此函数专门负责从 API 获取实时 Ticker 数据并写入数据库。
    """
    data = fetch_binance_ticker(symbol)

    if data:
        upsert_realtime_ticker(data)
    else:
        pass


def get_all_overview_data(symbol='BTCUSDT'):
    """
    从数据库读取最新的实时数据。
    """
    try:
        latest_data = get_latest_realtime_ticker(symbol)
        return latest_data
    except Exception as e:
        print(f"从数据库读取实时数据时发生错误：{e}")
        return None


def get_initial_data(symbol='BTCUSDT', interval='1d'):
    """
    只在数据库完全为空时运行一次，用于填充历史数据。
    """
    init_db()

    if not is_db_empty(symbol=symbol, interval=interval):
        return

    print(f"数据库为空，正在获取历史数据...")
    end_time = int(datetime.datetime.now().timestamp() * 1000)
    start_time_limit = int(datetime.datetime(2017, 8, 1, tzinfo=pytz.utc).timestamp() * 1000)

    all_new_data = pd.DataFrame()
    current_time = end_time

    while current_time > start_time_limit:
        print(
            f"正在从API获取历史数据，从 {datetime.datetime.fromtimestamp(current_time / 1000).strftime('%Y-%m-%d')} 往前...")

        temp_data = fetch_binance_klines(symbol=symbol, interval=interval, end_time=current_time, limit=1000)

        if temp_data is None or temp_data.empty:
            break

        if len(temp_data) < 1000:
            all_new_data = pd.concat([temp_data, all_new_data])
            break

        all_new_data = pd.concat([temp_data, all_new_data])
        current_time = int(all_new_data['open_time'].min().timestamp() * 1000) - 1
        time.sleep(0.5)

    if not all_new_data.empty:
        new_data_for_db = all_new_data.reset_index()
        insert_klines_data(new_data_for_db, symbol=symbol, interval=interval)
        print(f"成功获取并存储{len(all_new_data)}条历史数据。")
    else:
        print("未能从API获取历史数据。")


def sync_latest_klines_data(symbol='BTCUSDT', interval='1d'):
    """
    此函数负责：1. 补充失历史数据；2. 更新当天的 K 线数据。
    """
    latest_complete_ts = get_latest_complete_klines_timestamp(symbol=symbol, interval=interval)

    if not latest_complete_ts:
        return

    start_time_ms = latest_complete_ts + 1

    while True:
        yesterday_end_ms = int(
            (datetime.datetime.now(pytz.utc) - datetime.timedelta(days=1)).replace(hour=23, minute=59, second=59,
                                                                                   microsecond=999).timestamp() * 1000)

        if start_time_ms > yesterday_end_ms:
            print("所有历史K线数据都已是最新。")
            break

        temp_data = fetch_binance_klines(symbol=symbol, interval=interval, start_time=start_time_ms,
                                         end_time=yesterday_end_ms, limit=1000)

        if temp_data is None or temp_data.empty:
            break

        new_data_to_add = temp_data.reset_index()
        insert_klines_data(new_data_to_add, symbol=symbol, interval=interval)

        if len(temp_data) < 1000:
            break

        start_time_ms = int(temp_data.index.max().timestamp() * 1000) + 1
        time.sleep(0.5)

    # 获取今天的数据并覆盖
    today = datetime.datetime.now(pytz.utc).date()
    end_time_ms = int(datetime.datetime.now(pytz.utc).timestamp() * 1000)
    start_time_ms = int(datetime.datetime.combine(today, datetime.time.min, pytz.utc).timestamp() * 1000)
    today_data = fetch_binance_klines(symbol=symbol, interval=interval, start_time=start_time_ms, end_time=end_time_ms,
                                      limit=10)

    if today_data is not None and not today_data.empty:
        insert_klines_data(today_data.reset_index(), symbol=symbol, interval=interval)
    else:
        print("未能获取当天K线数据，跳过更新。")


def sync_latest_fgi_data():
    """
    智能同步 FGI 数据。
    """

    latest_db_date = get_latest_fgi_timestamp()
    today = datetime.date.today()
    days_to_fetch = 730

    if latest_db_date is not None:
        delta = today - latest_db_date
        days_to_fetch = delta.days + 1

        if latest_db_date == today:
            return

        if days_to_fetch < 1:
            return

    else:
        print(f"数据库中FGI数据为空，将获取{days_to_fetch}天的历史数据。")

    fgi_all_df = get_historical_fear_and_greed_data(days_limit=days_to_fetch)

    if fgi_all_df.empty or 'FGI' not in fgi_all_df.columns:
        return

    if latest_db_date:
        fgi_new_data = fgi_all_df[fgi_all_df.index.date > latest_db_date]
    else:
        fgi_new_data = fgi_all_df

    if fgi_new_data.empty:
        return

    upsert_fgi_data(fgi_new_data)


def sync_only_ticker(symbol='BTCUSDT'):
    """【轻量级】仅同步实时价格，适合极高频调用"""
    sync_realtime_ticker(symbol)
    return True

def sync_daily_stats(symbol='BTCUSDT', interval='1d'):
    """【重量级】同步K线和FGI，适合低频调用（如每小时）"""
    sync_latest_klines_data(symbol, interval)
    sync_latest_fgi_data()
    return True

def full_data_sync(symbol='BTCUSDT', interval='1d'):
    """保留原函数名，防止其他地方调用报错"""
    sync_only_ticker(symbol)
    sync_daily_stats(symbol, interval)
    return True