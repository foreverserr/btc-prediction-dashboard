# 文件: fetch/fgi_data.py

import requests
import pandas as pd
import datetime
from db import upsert_fgi_data

# 外部 API 配置
FGI_API_URL = "https://api.alternative.me/fng/?limit={limit}"
DEFAULT_FGI_DAYS_LIMIT = 730


# 1. 核心函数：获取 FGI 数据 (情绪指标)
def get_historical_fear_and_greed_data(days_limit=DEFAULT_FGI_DAYS_LIMIT):
    """
    从 Alternative.me API 获取历史恐惧与贪婪指数 (FGI) 数据。
    返回以 close_time 为索引的 DataFrame，且数据已按日期升序排列。
    """
    # 强制将请求天数限制在 7 天内，以防传入错误的 days_limit
    if days_limit > DEFAULT_FGI_DAYS_LIMIT:
        days_limit = DEFAULT_FGI_DAYS_LIMIT

    try:
        response = requests.get(FGI_API_URL.format(limit=days_limit))
        response.raise_for_status()
        data = response.json()

    except requests.exceptions.RequestException as e:
        print(f"获取FGI数据失败(网络或连接问题): {e}")
        return pd.DataFrame()

    if 'data' not in data or not data['data']:
        print(f"API返回的数据格式不正确或数据为空。API响应摘要: {data.get('data')}")
        return pd.DataFrame()

    fgi_list = []
    for entry in data['data']:
        try:
            timestamp = int(entry['timestamp'])
            # 转换为 date 对象，以匹配数据库和 klines 的日期粒度
            fgi_list.append({
                'close_time': datetime.datetime.fromtimestamp(timestamp).date(),
                'FGI': int(entry['value'])
            })
        except ValueError as e:
            print(f"跳过无效时间戳/值数据: {entry}, 错误: {e}")
            continue

    fgi_df = pd.DataFrame(fgi_list)

    if fgi_df.empty:
        print("FGI 数据列表为空。")
        return pd.DataFrame()

    fgi_df.drop_duplicates(subset=['close_time'], keep='first', inplace=True)
    fgi_df.set_index('close_time', inplace=True)
    fgi_df.index = pd.to_datetime(fgi_df.index)

    # 强制升序排序（确保 ID=1 对应最老数据）
    fgi_df.sort_index(ascending=True, inplace=True)

    return fgi_df[['FGI']]


# 2. 辅助函数：统一获取和合并替代数据
def get_all_alternative_data(historical_df):
    """
    获取 FGI 数据并与传入的历史 K 线数据 (historical_df) 合并。
    """
    if historical_df.empty:
        # 数据库为空时的默认获取量改为 7
        days_limit = DEFAULT_FGI_DAYS_LIMIT
    else:
        # 获取足够的数据量，以覆盖历史 K 线数据
        days_limit = len(historical_df) + 30

    fgi_df = get_historical_fear_and_greed_data(days_limit=days_limit)

    final_df = historical_df.copy()

    # 统一索引格式
    if not final_df.empty:
        final_df.index = final_df.index.normalize()

    # 如果 historical_df 为空，并且 fgi_df 不为空，则直接使用 fgi_df
    if final_df.empty and not fgi_df.empty:
        final_df = fgi_df.copy()

    elif not final_df.empty and not fgi_df.empty:
        # 只有当 historical_df 和 fgi_df 都不为空时才进行 join
        final_df = final_df.join(fgi_df[['FGI']], how='left')

    # 处理只有 historical_df 为空的情况
    # 如果 historical_df 和 fgi_df 都为空，final_df 仍然是一个空的 DF
    # 只有在 final_df 不为空时才进行 ffill
    if not final_df.empty:
        # 使用 ffill 填充缺失值
        final_df = final_df.ffill()

    if 'FGI' in final_df.columns and final_df['FGI'].isnull().any():
            print("FGI 数据仍有缺失")
            pass

    return final_df


# --- 3. 主要执行函数：获取并存储 FGI 数据到数据库 ---
def fetch_and_store_fgi_data():
    """
    执行 FGI 数据采集任务，并将数据写入数据库。
    """

    empty_df = pd.DataFrame()

    # combined_df 此时只包含 FGI 数据（索引为 close_time）
    fgi_combined_df = get_all_alternative_data(empty_df)

    # 检查数据并写入数据库
    # 即使是空的 DataFrame，检查 'FGI' 列可能会报错，因此先检查 empty
    if fgi_combined_df.empty:
        print("无法获取 FGI 数据，跳过数据库写入。")
        return

    if 'FGI' not in fgi_combined_df.columns:
        print("获取的 FGI 数据中缺少 'FGI' 列，跳过数据库写入。")
        return

    # 调用新的数据库写入函数 (upsert_fgi_data 在 data_manager.py 中实现)
    upsert_fgi_data(fgi_combined_df)

    print(f"FGI数据采集和写入数据库任务完成，共{len(fgi_combined_df)}条数据 ---")


# --- 模块测试入口 ---
if __name__ == '__main__':
    fetch_and_store_fgi_data()