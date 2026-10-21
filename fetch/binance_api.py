import requests
import pandas as pd
import pytz
from datetime import datetime
import time

# 1. 全局 Session，复用连接
session = requests.Session()

# 这是国内备份节点：https://api.binance.cc/api/v3，实在不行就使用：https://api.binance.com/api/v3（需要梯子）
# BASE_URL = 'https://api.binance.me/api/v3'
BASE_URL = 'https://api.binance.com/api/v3'

def fetch_binance_klines(symbol='BTCUSDT', interval='1d', start_time=None, end_time=None, limit=1000):
    params = {'symbol': symbol, 'interval': interval, 'limit': limit}
    if start_time: params['startTime'] = start_time
    if end_time: params['endTime'] = end_time

    try:
        t_api_start = time.perf_counter()
        response = session.get(f"{BASE_URL}/klines", params=params, timeout=5)
        response.raise_for_status()
        klines = response.json()
    except Exception as e:
        print(f"K线获取失败: {e}")
        return None

    # 保持所有字段，特别是 close_time
    df = pd.DataFrame(klines, columns=['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time',
                                       'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume',
                                       'taker_buy_quote_asset_volume', 'ignore'])

    # --- 修复点：确保包含 close_time ---
    df = df[['open_time', 'close_time', 'open', 'high', 'low', 'close', 'volume']]

    # 转换时间格式
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms').dt.tz_localize(pytz.utc)
    df['close_time'] = pd.to_datetime(df['close_time'], unit='ms').dt.tz_localize(pytz.utc)

    df = df.astype({'open': float, 'high': float, 'low': float, 'close': float, 'volume': float})
    return df


def fetch_binance_ticker(symbol='BTCUSDT'):
    """
    获取当前日线级别的行情数据，（数据起止时间为 UTC 0点，即北京时间 08:00）。
    """
    try:
        t_start = time.perf_counter()
        params = {'symbol': symbol, 'limit': 1, 'interval': '1d'}
        res = session.get(f"{BASE_URL}/klines", params=params, timeout=3)
        res.raise_for_status()
        klines = res.json()

        if not klines:
            return None

        latest_day = klines[0]

        open_price = float(latest_day[1])
        high_price = float(latest_day[2])
        low_price = float(latest_day[3])
        last_price = float(latest_day[4])  # 当前最新价就是收盘价
        volume = float(latest_day[5])

        # 计算涨跌幅
        price_change_percent = ((last_price - open_price) / open_price) * 100 if open_price != 0 else 0.0

        # 测试获取数据的时间
        # print(f"获取最新日线行情耗时: {time.perf_counter() - t_start:.4f}s")

        return {
            'symbol': symbol,
            'lastPrice': last_price,
            'priceChangePercent': price_change_percent,
            'highPrice': high_price,
            'lowPrice': low_price,
            'openPrice': open_price,
            'volume': volume
        }
    except Exception as e:
        print(f"实时行情获取失败: {e}")
        return None