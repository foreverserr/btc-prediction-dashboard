# fetchs/__init__.py

# --- 1. 从 binance_api.py 导出所有 API 客户端函数 (底层数据获取) ---
from .binance_api import (
    fetch_binance_klines,
    fetch_binance_ticker,
)

# --- 2. 从 data_sync.py 导出所有数据同步和读取的公共函数 (业务逻辑) ---
from .data_sync import (
    sync_realtime_ticker,
    get_all_overview_data,
    get_initial_data,
    sync_latest_klines_data,
    full_data_sync,
    sync_only_ticker,
    sync_daily_stats
)

from .fgi_data import (
    fetch_and_store_fgi_data,
)