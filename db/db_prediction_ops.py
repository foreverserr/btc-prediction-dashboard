# db/db_prediction_ops.py

import pandas as pd
import datetime
import pytz
import mysql.connector

# 导入连接函数和数据读取函数
from .db_connect import get_conn_from_pool
from .db_pandas_query import _get_raw_klines_for_prediction, get_historical_fgi_data


# FGI 数据合并

def get_fgi_data_for_merge(historical_df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    从数据库加载 FGI 数据，并将其与 K 线数据合并。

    参数: historical_df_raw: K 线历史数据 DataFrame，包含 'close_time' (UTC) 列。
    返回: 合并后的 DataFrame，新增 'FGI' 列。
    """
    print("正在加载 FGI 数据并与 K 线数据合并... ")

    fgi_data_raw = get_historical_fgi_data()

    if fgi_data_raw.empty:
        print("fgi_data 表中无数据。使用默认值 50.0 填充 FGI 列。")
        historical_df_raw.set_index('close_time', inplace=True)
        historical_df_raw['FGI'] = 50.0
        return historical_df_raw.copy()

    historical_df = historical_df_raw.copy()

    if pd.api.types.is_datetime64_any_dtype(historical_df['close_time']):
        historical_df['merge_key'] = historical_df['close_time'].dt.normalize()
    else:
        historical_df.set_index('close_time', inplace=True)
        historical_df['FGI'] = 50.0
        return historical_df.copy()

    fgi_data_raw.reset_index(inplace=True)

    # 左连接合并
    merged_df = pd.merge(
        historical_df,
        fgi_data_raw[['close_time', 'FGI']],
        left_on='merge_key',
        right_on='close_time',
        how='left',
        suffixes=('_klines', '_fgi')
    )

    # 清理和填充
    merged_df.drop(columns=['merge_key', 'close_time_fgi'], inplace=True)
    merged_df.rename(columns={'close_time_klines': 'close_time'}, inplace=True)

    nan_count = merged_df['FGI'].isna().sum()
    if nan_count > 0:
        # 填充缺失值为 50.0
        merged_df['FGI'] = merged_df['FGI'].fillna(50.0)
    merged_df['FGI'] = merged_df['FGI'].astype(float)

    merged_df.set_index('close_time', inplace=True)

    print(
        f"FGI 数据已成功从数据库合并。K 线数据总数: {len(historical_df_raw)}, FGI 非空计数: {len(merged_df.dropna(subset=['FGI']))}")
    return merged_df


def get_prediction_klines_data(symbol='BTCUSDT', interval='1d') -> pd.DataFrame:
    """
    为预测模型获取所有历史 K 线数据，并包含 FGI 特征。
    """
    historical_df_raw = _get_raw_klines_for_prediction(symbol, interval)

    if historical_df_raw.empty:
        print("数据库中没有可用的 K 线数据。")
        return pd.DataFrame()

    merged_df_with_fgi = get_fgi_data_for_merge(historical_df_raw)

    return merged_df_with_fgi


# 预测结果存储

def save_predictions_to_db(last_real_price: float, historical_df_processed: pd.DataFrame,
                           predicted_prices_inversed: list, FUTURE_DAYS: int = 7):
    """
    将 P(t-1) 的基准价格和 T+1 到 T+7 的预测价格保存到 future_predictions 表中。
    """
    local_tz = pytz.timezone("Asia/Shanghai")
    current_prediction_time_local = datetime.datetime.now(local_tz)

    conn = get_conn_from_pool()
    if not conn:
        print("致命错误: 无法连接数据库，跳过结果储存。")
        return

    cursor = None
    try:
        cursor = conn.cursor()

        # 1. 清空旧数据 (TRUNCATE)
        cursor.execute("TRUNCATE TABLE future_predictions")
        conn.commit()

        # 2. 准备插入数据 (INSERT)
        query = """
            INSERT INTO future_predictions (close_time, prediction_time, predicted_price)
            VALUES (%s, %s, %s)
            """
        records = []

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

        # 插入 T+1 到 T+FUTURE_DAYS 的预测价格
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
        print(f"--- 预测结果 (未来 {FUTURE_DAYS} 天曲线) 成功储存到数据库！ ---")

    except mysql.connector.Error as err:
        print(f"[DB_PREDICTION_ERROR] 储存预测结果失败 (MySQL 错误): {err}")
    except Exception as e:
        print(f"[DB_PREDICTION_ERROR] 储存预测结果失败 (通用错误): {e}")
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()