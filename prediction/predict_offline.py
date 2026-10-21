import pandas as pd
import numpy as np
import tensorflow as tf
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.layers import LSTM, Dense, Dropout, Attention, Concatenate
from tensorflow.keras.models import load_model
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
from tensorflow.keras.regularizers import l2
import datetime
import os
import mysql.connector
import pytz
import joblib
import logging
import sys

# 设置Tensorflow日志级别为ERROR
tf.get_logger().setLevel(logging.ERROR)

# 数据库依赖导入和 Mock
from db import get_prediction_klines_data, get_conn_from_pool, get_fgi_data_for_merge, get_latest_realtime_ticker

# 配置常量
MODEL_PATH = 'btc_usdt_lstm_model.keras'
PRICE_SCALER_PATH = 'price_scaler.joblib'
DIFF_SCALER_PATH = 'diff_scaler.joblib'
VOLUME_SCALER_PATH = 'volume_scaler.joblib'
RSI_SCALER_PATH = 'rsi_scaler.joblib'
MACD_SCALER_PATH = 'macd_scaler.joblib'
FGI_SCALER_PATH = 'fgi_scaler.joblib'

PREDICTION_DAYS = 7
FUTURE_DAYS = 7

ADDITIONAL_FEATURES = ['volume', 'RSI', 'MACD_Signal', 'FGI']
FEATURES = ['close', 'Price_Diff'] + ADDITIONAL_FEATURES

L2_RATE_TRAIN = 0.0001
LR_INITIAL_TRAIN = 0.0008
LR_FINE_TUNE = 0.0002

# FGI 宏观趋势相关参数
FGI_TREND_WINDOW = 7
# 降低基础日偏差权重，以减少极度FGI对预测的主导程度
MAX_FGI_BIAS_PER_DAY = 0.0025
# 降低极度 FGI 区域的放大倍数，避免极端下跌
FGI_EXTREME_MULTIPLIER = 2.0
MOMENTUM_MULTIPLIER = 1.2

# 动态波动参数
NOISE_STD_DEV = 0.005
MIN_T1_CHANGE_FOR_AMPLIFY = 0.003
MAX_VOLATILITY_MULTIPLIER = 2.5


# 保存预测结果到数据库
def save_predictions_to_db(last_real_price: float, historical_df_processed: pd.DataFrame,
                           predicted_prices_inversed: list):
    """
    将 P(t-1) 的基准价格和 T+1 到 T+7 的预测价格保存到数据库。
    """
    local_tz = pytz.timezone("Asia/Shanghai")
    current_prediction_time_local = datetime.datetime.now(local_tz)

    conn = get_conn_from_pool()
    if not conn:
        print("无法连接数据库，跳过结果储存。")
        return

    cursor = None
    try:
        cursor = conn.cursor()

        # 1. 清空旧数据
        cursor.execute("TRUNCATE TABLE future_predictions")
        conn.commit()

        # 2. 准备插入数据
        query = """
            INSERT INTO future_predictions (close_time, prediction_time, predicted_price)
            VALUES (%s, %s, %s)
            """
        records = []

        # 获取 T-1 的时间戳
        base_close_time = historical_df_processed.index[-1]
        if hasattr(base_close_time, 'to_pydatetime'):
            base_close_time = base_close_time.to_pydatetime()

        prediction_time_standard = current_prediction_time_local
        last_close_price_float = float(last_real_price)

        # 插入基准价格 P(t-1)
        records.append((
            base_close_time,
            prediction_time_standard,
            last_close_price_float,
        ))

        # 插入 T+1 到 T+7 的预测价格
        for i in range(FUTURE_DAYS):
            prediction_datetime = historical_df_processed.index[-1] + pd.Timedelta(days=i + 1)
            if hasattr(prediction_datetime, 'to_pydatetime'):
                prediction_datetime = prediction_datetime.to_pydatetime()

            predicted_price_float = float(predicted_prices_inversed[i])

            records.append((
                prediction_datetime,
                prediction_time_standard,
                predicted_price_float,
            ))

        # 3. 执行批量插入
        cursor.executemany(query, records)
        conn.commit()
        print(f"预测结果成功储存到数据库！")

    except mysql.connector.Error as err:
        print(f"储存预测结果失败 (MySQL 错误): {err}")
    except Exception as e:
        print(f"储存预测结果失败 (通用错误): {e}")
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


# 技术指标计算函数
def calculate_all_features(df):
    """计算价格差异、RSI和MACD指标。"""
    #计算价格差异
    df['Price_Diff'] = df['close'].diff()
    delta = df['close'].diff()
    #计算RSI
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    #指数加权
    avg_gain = gain.ewm(span=14, adjust=False).mean()
    avg_loss = loss.ewm(span=14, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, 1e-10)
    df['RSI'] = 100 - (100 / (1 + rs))

    #计算MACD
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    df['MACD_Signal'] = macd.ewm(span=9, adjust=False).mean()

    df['Price_Diff'] = df['Price_Diff'].fillna(0)
    return df.dropna().copy()


# FGI 情绪趋势偏差计算
def calculate_fgi_sentiment_bias(df: pd.DataFrame, window: int) -> tuple[float, float]:
    """
    根据 FGI 均值计算日内趋势偏差，并应用非线性放大器。
    """
    if 'FGI' not in df.columns:
        print("FGI 宏观趋势计算失败，缺失FGI数据")
        return 0.0, 50.0

    fgi_data = df['FGI'].iloc[-window:].copy()

    if fgi_data.empty:
        return 0.0, 50.0

    avg_fgi = fgi_data.mean()

    # FGI 越低，偏差越负（看跌）。
    deviation_from_neutral = avg_fgi - 50.0
    normalized_deviation = deviation_from_neutral / 50.0

    amplification_factor = 1.0

    # 极度区放大 (FGI < 25 或 FGI > 75)
    if avg_fgi < 25 or avg_fgi > 75:
        # 极度区放大，使用调整后的 FGI_EXTREME_MULTIPLIER
        amplification_factor = FGI_EXTREME_MULTIPLIER
    # 强力区放大 (FGI < 35 或 FGI > 65)
    elif avg_fgi < 35 or avg_fgi > 65:
        amplification_factor = 1.5

    # 使用MAX_FGI_BIAS_PER_DAY计算趋势偏差
    trend_bias = normalized_deviation * MAX_FGI_BIAS_PER_DAY * amplification_factor

    MAX_HARD_LIMIT = 0.012
    trend_bias = np.clip(trend_bias, -MAX_HARD_LIMIT, MAX_HARD_LIMIT)

    return float(trend_bias), float(avg_fgi)


# 创建 Seq2Seq 数据
def create_seq2seq_data(scaled_input_data, raw_data_for_target):
    X_train = []
    y_train_rel_change = []

    for i in range(PREDICTION_DAYS, len(raw_data_for_target) - FUTURE_DAYS + 1):
        X_train.append(scaled_input_data[i - PREDICTION_DAYS:i, :])
        P_t = raw_data_for_target['close'].iloc[i - 1]
        future_prices = raw_data_for_target['close'].iloc[i:i + FUTURE_DAYS].values
        relative_change = (future_prices - P_t) / P_t
        y_train_rel_change.append(relative_change)

    return np.array(X_train), np.array(y_train_rel_change)


# 辅助函数：构建、训练或微调 Seq2Seq 模型
def train_or_finetune_model(X_train, y_train_rel_change, existing_model=None):
    """构建、训练或微调 Seq2Seq 模型，并根据模式调整学习率。"""
    MAX_EPOCHS = 120 if existing_model is None else 30
    PATIENCE = 12 if existing_model is None else 8
    L2_RATE = L2_RATE_TRAIN

    if existing_model:
        model = existing_model
        learning_rate = LR_FINE_TUNE
        print(f"正在对现有模型进行微调 (Max Epochs: {MAX_EPOCHS}, LR: {learning_rate})... ")
    else:
        learning_rate = LR_INITIAL_TRAIN
        print(
            f"正在构建和训练新的价格模型 (LR: {learning_rate}, 微弱 L2:{L2_RATE}, 特征数:{X_train.shape[2]})... ")

        input_layer = tf.keras.Input(shape=(X_train.shape[1], X_train.shape[2]))

        encoder_output = LSTM(384, return_sequences=True, kernel_regularizer=l2(L2_RATE))(input_layer)
        encoder_output = Dropout(0.6)(encoder_output)

        attention_output = Attention(use_scale=True)([encoder_output, encoder_output])
        context_vector = Concatenate(axis=-1)([encoder_output, attention_output])

        decoder_input = LSTM(192, return_sequences=False, kernel_regularizer=l2(L2_RATE))(context_vector)

        decoder_output = Dropout(0.6)(decoder_input)
        decoder_output = Dense(96, activation='relu', kernel_regularizer=l2(L2_RATE))(decoder_output)
        decoder_output = Dropout(0.4)(decoder_output)
        final_output = Dense(FUTURE_DAYS)(decoder_output)

        model = tf.keras.Model(inputs=input_layer, outputs=final_output)

    optimizer = tf.keras.optimizers.Adam(learning_rate=learning_rate)
    model.compile(optimizer=optimizer, loss='mean_squared_error')

    callbacks = [
        EarlyStopping(monitor='val_loss', patience=PATIENCE, verbose=1, mode='min'),
        ModelCheckpoint(filepath=MODEL_PATH, monitor='val_loss', save_best_only=True, verbose=0)
    ]

    model.fit(X_train, y_train_rel_change,
              batch_size=32,
              epochs=MAX_EPOCHS,
              verbose=0,
              callbacks=callbacks,
              validation_split=0.1)

    # print(f"Seq2Seq 相对变化率模型训练/微调完成！最佳权重已保存至 {MODEL_PATH} ")

    best_model = load_model(MODEL_PATH)
    return best_model


def build_and_train_model(X_train, y_train_rel_change):
    """首次构建和训练模型。"""
    return train_or_finetune_model(X_train, y_train_rel_change, existing_model=None)


# 模型预测和结果储存函数
def run_and_save_prediction():
    """执行完整的模型训练/加载和预测流程。"""
    historical_df_raw = get_prediction_klines_data(symbol='BTCUSDT', interval='1d')
    ticker_data = get_latest_realtime_ticker('BTCUSDT')

    new_row_time = historical_df_raw.index[-1] + pd.Timedelta(days=1)
    new_row = pd.DataFrame({
        'close': [ticker_data['lastPrice']],
        'volume': [ticker_data['volume']]
    }, index=[new_row_time])
    historical_df_raw = pd.concat([historical_df_raw, new_row])

    if 'FGI' not in historical_df_raw.columns and 'FGI' in FEATURES:
        original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
        try:
            historical_df_raw = get_fgi_data_for_merge(historical_df_raw)
        finally:
            sys.stdout.close()
            sys.stdout = original_stdout

    if 'FGI' not in historical_df_raw.columns and 'FGI' in FEATURES:
        print("无法获取FGI数据，请检查数据源。")
        return

    historical_df_processed = calculate_all_features(historical_df_raw.copy())

    if len(historical_df_processed) < PREDICTION_DAYS + FUTURE_DAYS:
        print(f"数据准备失败，跳过预测。")
        return

    print(f"数据准备完成.")

    last_real_data = historical_df_processed.iloc[-1]
    last_real_price = last_real_data['close']

    fgi_sentiment_bias, avg_fgi_7d = calculate_fgi_sentiment_bias(
        historical_df_processed,
        window=FGI_TREND_WINDOW
    )

    scalers = {}
    scaled_features = {}

    price_scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_features['close'] = price_scaler.fit_transform(historical_df_processed[['close']].values)
    scalers['close'] = price_scaler

    diff_scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_features['Price_Diff'] = diff_scaler.fit_transform(historical_df_processed[['Price_Diff']].values)
    scalers['Price_Diff'] = diff_scaler

    for feature in ADDITIONAL_FEATURES:
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaled_features[feature] = scaler.fit_transform(historical_df_processed[[feature]].values)
        scalers[feature] = scaler

    if 'FGI' in FEATURES:
        joblib.dump(scalers['FGI'], FGI_SCALER_PATH)

    scaled_input_data = np.hstack([scaled_features[f] for f in FEATURES])

    try:
        joblib.dump(scalers['close'], PRICE_SCALER_PATH)
        joblib.dump(scalers['Price_Diff'], DIFF_SCALER_PATH)
        joblib.dump(scalers['volume'], VOLUME_SCALER_PATH)
        joblib.dump(scalers['RSI'], RSI_SCALER_PATH)
        joblib.dump(scalers['MACD_Signal'], MACD_SCALER_PATH)
        print(f"{len(FEATURES)} 个特征的归一化器已保存")
    except Exception as e:
        print(f"归一化器保存失败 ({e})。")

    # 数据准备 Seq2Seq
    X_train, y_train_rel_change = create_seq2seq_data(scaled_input_data, historical_df_processed)

    # 模型加载/训练
    model = None
    if os.path.exists(MODEL_PATH):
        try:
            existing_model = load_model(MODEL_PATH)
            if existing_model.input_shape[-1] != len(FEATURES) or existing_model.input_shape[1] != PREDICTION_DAYS:
                model = build_and_train_model(X_train, y_train_rel_change)
            else:
                model = train_or_finetune_model(X_train, y_train_rel_change, existing_model=existing_model)
        except Exception as e:
            model = build_and_train_model(X_train, y_train_rel_change)
    else:
        model = build_and_train_model(X_train, y_train_rel_change)

    if model is None:
        print("无法加载、训练或微调主模型，跳过预测。")
        return

    # --- 预测和自回归循环 (保持不变) ---
    last_close_timestamp = int(historical_df_processed.index[-1].timestamp())
    np.random.seed(last_close_timestamp)

    current_input_data = scaled_input_data[-PREDICTION_DAYS:].copy()
    X_test_baseline = current_input_data.reshape(1, PREDICTION_DAYS, len(FEATURES))
    baseline_rel_changes = model.predict(X_test_baseline, verbose=0)[0]

    t1_abs_change = abs(baseline_rel_changes[0])
    volatility_multiplier = 1.0
    if t1_abs_change > MIN_T1_CHANGE_FOR_AMPLIFY:
        multiplier_increase = (t1_abs_change - MIN_T1_CHANGE_FOR_AMPLIFY) / (0.005)
        volatility_multiplier = 1.0 + multiplier_increase
        volatility_multiplier = min(volatility_multiplier, MAX_VOLATILITY_MULTIPLIER)

    SIMULATION_STD_DEV = NOISE_STD_DEV * volatility_multiplier

    print(
        f"T+1 模型变化率：{t1_abs_change * 100:.2f}%，波动放大倍数：{volatility_multiplier:.2f}x，模拟 Sigma：{SIMULATION_STD_DEV * 100:.2f}% ")

    # 注意：fgi_sentiment_bias 现在是负值，将进一步强化下跌趋势。
    fgi_direction = "看涨 (Greed)" if fgi_sentiment_bias > 0 else "看跌 (Fear)" if fgi_sentiment_bias < 0 else "中性"
    print(
        f" FGI趋势：FGI 7D均值 {avg_fgi_7d:.2f} 确定为 {fgi_direction} (日偏差率: {fgi_sentiment_bias * 100:.3f}%) ")

    print(f"\n开始预测")

    predicted_prices_inversed = []
    current_price_for_diff = last_real_price

    price_scaler = scalers['close']
    diff_scaler = scalers['Price_Diff']
    fgi_scaler = scalers['FGI']

    last_real_fgi = historical_df_processed.iloc[-1]['FGI']
    scaled_fgi_value = fgi_scaler.transform(np.array([[last_real_fgi]]))[0, 0]

    CLOSE_IDX = FEATURES.index('close')
    DIFF_IDX = FEATURES.index('Price_Diff')
    VOL_IDX = FEATURES.index('volume')
    RSI_IDX = FEATURES.index('RSI')
    MACD_IDX = FEATURES.index('MACD_Signal')
    FGI_IDX = FEATURES.index('FGI')

    # 确定是否处于极度 FGI 区域，以调整衰减率，确保顺势趋势更持久
    fgi_is_extreme = (avg_fgi_7d < 25 or avg_fgi_7d > 75)

    for i in range(FUTURE_DAYS):
        # 动态调整动量衰减率，极度 FGI 时衰减慢，使顺势趋势持续
        if fgi_is_extreme:
            # 极度 FGI 时，动量衰减较慢 (0.6)
            decay_rate = 0.6
        else:
            # 正常情况下，动量衰减较快 (0.9)
            decay_rate = 0.9

        momentum_decay_factor = 1.0 - (i / (FUTURE_DAYS - 1)) * decay_rate

        R_i = baseline_rel_changes[i]
        R_i_minus_1 = baseline_rel_changes[i - 1] if i > 0 else 0

        daily_model_momentum = (1 + R_i) / (1 + R_i_minus_1 + 1e-8) - 1
        daily_model_momentum *= MOMENTUM_MULTIPLIER

        daily_noise = np.random.normal(loc=0.0, scale=SIMULATION_STD_DEV)

        # FGI 偏差现在是负值，但它的绝对值已经通过参数调整被降低。
        daily_change_rate = (daily_model_momentum * momentum_decay_factor) + fgi_sentiment_bias + daily_noise
        daily_change_rate = np.clip(daily_change_rate, -0.025, 0.025)

        predicted_price = current_price_for_diff * (1 + daily_change_rate)
        predicted_prices_inversed.append(predicted_price)

        cumulative_rel_change = (predicted_price - last_real_price) / last_real_price

        print(
            f" 预测完成 第 {i + 1} 天 (动量衰减: {momentum_decay_factor:.2f}): {predicted_price:.2f} (相对P(t)变化率: {cumulative_rel_change * 100:.2f}%)")

        predicted_diff = predicted_price - current_price_for_diff

        new_row_features = [0] * len(FEATURES)
        new_row_features[CLOSE_IDX] = price_scaler.transform(np.array([[predicted_price]]))[0, 0]
        new_row_features[DIFF_IDX] = diff_scaler.transform(np.array([[predicted_diff]]))[0, 0]
        new_row_features[VOL_IDX] = current_input_data[-1, VOL_IDX]
        new_row_features[RSI_IDX] = current_input_data[-1, RSI_IDX]
        new_row_features[MACD_IDX] = current_input_data[-1, MACD_IDX]
        new_row_features[FGI_IDX] = scaled_fgi_value

        next_features = np.array([new_row_features])
        current_input_data = np.vstack([current_input_data[1:], next_features])
        current_price_for_diff = predicted_price

    save_predictions_to_db(last_real_price, historical_df_processed, predicted_prices_inversed)


if __name__ == '__main__':

    run_and_save_prediction()