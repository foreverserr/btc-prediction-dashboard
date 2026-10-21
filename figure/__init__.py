# figure/__init__.py

# --- 布林带 (Bollinger Bands) ---
from .figure_bollinger import (
    calculate_bollinger_bands,
    get_bollinger_traces
)

# --- 每日回报率 (Daily Return) ---
from .figure_daily_return import (
    calculate_daily_return,
    get_daily_return_traces
)

# --- 移动平均线 (Moving Average) ---
from .figure_ma import (
    get_price_and_ma_traces
)

# --- MACD ---
from .figure_macd import (
    calculate_macd,
    get_macd_traces
)

# --- 预测器 (Predictor) ---
from .figure_prediction import (
    create_prediction_figure
)

# --- RSI (Relative Strength Index) ---
from .figure_rsi import (
    calculate_rsi,
    get_rsi_traces
)

# --- 成交量 (Volume) ---
from .figure_volume import (
    get_volume_traces
)