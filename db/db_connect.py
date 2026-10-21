# db/db_connect.py

import mysql.connector
from mysql.connector import pooling
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

# 将这些参数替换为你自己的数据库设置
DB_PARAMS = {
    'host': 'localhost',
    'user': 'root',
    'password': '123456',
    'database': 'btc_analysis'
}

# --- SQLAlchemy Engine 初始化 ---
# ⭐ 【新增】构建 SQLAlchemy 的连接 URI
# 格式: 'mysql+mysqlconnector://user:password@host/database'
DATABASE_URI = (
    f"mysql+mysqlconnector://{DB_PARAMS['user']}:{DB_PARAMS['password']}@"
    f"{DB_PARAMS['host']}/{DB_PARAMS['database']}"
)

# 使用全局变量存储 Engine
SQL_ENGINE: Engine = None
try:
    # ⭐ 【新增】创建并存储 SQLAlchemy Engine
    # pool_pre_ping=True 用于确保连接有效
    SQL_ENGINE = create_engine(DATABASE_URI, pool_pre_ping=True)
except Exception as e:
    # 打印错误但不影响后续的 mysql.connector 连接
    print(f"无法建立 SQLAlchemy Engine: {e}")


# --- 连接池初始化 (保留，用于日志或非 Pandas 的 cursor 操作) ---
connection_pool = None
try:
    connection_pool = pooling.MySQLConnectionPool(
        pool_name="my_pool",
        pool_size=5,
        **DB_PARAMS
    )
    print("数据库连接池初始化成功。")
except mysql.connector.Error as err:
    print(f"无法建立数据库连接池: {err}")


def connect_db():
    """建立单一数据库连接。"""
    try:
        return mysql.connector.connect(**DB_PARAMS)
    except mysql.connector.Error as err:
        print(f"无法建立单一数据库连接: {err}")
        return None


def get_conn_from_pool():
    """
    从连接池获取原生的 mysql.connector 连接。
    (主要用于 init_db, log_handler, login 等需要 cursor 的操作)
    """
    conn = None
    if connection_pool:
        try:
            conn = connection_pool.get_connection()
        except mysql.connector.Error as err:
            print(f"从连接池获取连接时出错: {err}，尝试建立单一连接。")
            conn = connect_db()
    else:
        conn = connect_db()

    if not conn or not conn.is_connected():
        print("无法建立数据库连接。")
        return None

    return conn

# ⭐ 【新增】导出 SQLAlchemy Engine 的函数
def get_sql_engine():
    """返回 SQLAlchemy Engine 对象，用于 Pandas/SQL 读写操作。"""
    if SQL_ENGINE is None:
        print("SQLAlchemy Engine 未初始化！")
    return SQL_ENGINE


def init_db():
    """初始化数据库表结构。"""
    conn = get_conn_from_pool()
    if not conn:
        return

    cursor = None
    try:
        cursor = conn.cursor()
        # 1. K线数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS klines_data (
                id INT AUTO_INCREMENT PRIMARY KEY,
                update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                symbol VARCHAR(20) NOT NULL,
                `interval` VARCHAR(10) NOT NULL,
                open_time DATETIME NOT NULL,
                close_time DATETIME NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                UNIQUE KEY `unique_klines` (`symbol`, `interval`, `open_time`)
            )
        ''')
        # 2. 实时行情表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS realtime_ticker (
                symbol VARCHAR(20) PRIMARY KEY,
                lastPrice REAL,
                priceChangePercent REAL,
                highPrice REAL,
                lowPrice REAL,
                openPrice REAL,
                volume REAL,
                fetch_time DATETIME
            )
        ''')
        # 3. 用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL,
                session_token VARCHAR(255) NULL
            )
        ''')
        # 4. 预测数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS future_predictions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                prediction_time DATETIME NOT NULL,
                predicted_price REAL NOT NULL,
                close_time DATETIME NOT NULL
            )
        ''')
        # 5. 日志/审计表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                timestamp DATETIME NOT NULL,
                operator VARCHAR(100) NOT NULL,
                action_type VARCHAR(50) NOT NULL,
                target_user VARCHAR(100),
                status VARCHAR(10) NOT NULL,
                message TEXT,
                INDEX idx_operator (operator),
                INDEX idx_target_user (target_user)
            )
        ''')
        # 6. 服务器/系统日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS server_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                timestamp DATETIME NOT NULL,         
                level VARCHAR(10) NOT NULL,          
                module VARCHAR(50) NOT NULL,         
                message TEXT,                        
                ip_address VARCHAR(40),              
                request_path VARCHAR(255),           
                status_code INT                      
            )
        ''')

        # 5. 市场情绪指标表 (FGI)
        cursor.execute('''
                    CREATE TABLE IF NOT EXISTS fgi_data (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        close_date DATE NOT NULL,
                        fgi_value INT NOT NULL,
                        UNIQUE KEY `unique_fgi_date` (`close_date`)
                    )
                ''')

        conn.commit()
        print("数据库表结构检查/初始化完成。")
    except mysql.connector.Error as err:
        print(f"数据库初始化失败: {err}")
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()
