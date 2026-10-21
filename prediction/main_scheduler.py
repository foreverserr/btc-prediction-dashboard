# main_scheduler.py

from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import datetime
import pytz

try:
    # 假设预测函数在 prediction 模块下的 predict_offline 文件中
    from prediction.predict_offline import run_and_save_prediction

    # 定义包装器函数，用于捕获预测脚本内部的异常
    def wrapped_prediction_task():
        tz = pytz.timezone("Asia/Shanghai")
        start_time = datetime.datetime.now(tz)
        print(f"调度任务开始执行: {start_time.strftime('%Y-%m-%d %H:%M:%S')} (UTC+8) ---")
        try:
            run_and_save_prediction()
            print(f"任务执行成功! 耗时: {datetime.datetime.now(tz) - start_time} ---")
        except Exception as e:
            print(f"预测函数内部执行失败！")
            print(f"错误详情: {e}")

except ImportError as e:
    print(f"无法导入预测函数 'run_and_save_prediction'，调度器将不会启动。错误详情: {e}")
    wrapped_prediction_task = None


def start_scheduler():
    """
    启动 APScheduler 调度器。
    """
    if not wrapped_prediction_task:
        return

    tz = pytz.timezone("Asia/Shanghai")
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    # 1. 每日定时任务：每天 13:00 运行
    scheduler.add_job(
        wrapped_prediction_task,
        trigger='cron',
        hour=13,
        minute=00,
        id='daily_btc_prediction',
        name='Daily BTCUSDT Prediction Run'
    )

    # 2. 临时调试任务：启动后 10 秒执行 (用于验证启动是否成功)
    now_plus_10_sec = datetime.datetime.now(tz) + datetime.timedelta(seconds=10)
    scheduler.add_job(
        wrapped_prediction_task,
        trigger='date',
        run_date=now_plus_10_sec,
        id='test_run',
        name='Immediate Test Run'
    )

    print("--- 预测模型调度器启动 ---")
    scheduler.print_jobs()

    # 启动调度器
    scheduler.start()

    # 注册退出函数
    atexit.register(lambda: scheduler.shutdown())

    print("调度器已在后台启动，等待Dash应用服务器保持进程活跃...")


if __name__ == '__main__':
    start_scheduler()
    print("调度器已启动。按 Ctrl+C 退出...")

    import time

    try:
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        print("调度器退出。")