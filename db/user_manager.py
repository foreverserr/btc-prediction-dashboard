# user_manager.py

import pandas as pd
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import uuid
from db import get_conn_from_pool, get_sql_engine
import datetime


class User(UserMixin):
    """
    用户模型，继承自 Flask-Login 的 UserMixin。
    """

    def __init__(self, user_id, username, password_hash, role):
        self.id = user_id
        self.username = username
        self.password_hash = password_hash
        self.role = role

    def get_id(self):
        return str(self.id)


def get_user_by_username(username):
    """根据用户名查找用户对象。（使用原生连接）"""
    conn = get_conn_from_pool()
    if not conn: return None
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT id, username, password_hash, role FROM users WHERE username = %s"
        cursor.execute(query, (username,))
        user_data = cursor.fetchone()
        if user_data:
            return User(
                user_data['id'],
                user_data['username'],
                user_data['password_hash'],
                user_data['role']
            )
        return None
    except mysql.connector.Error as err:
        print(f"获取用户失败: {err}")
        return None
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()


def get_user_by_id(user_id):
    """根据用户ID查找用户数据 (主要供 Flask-Login 的 user_loader 使用)。"""
    conn = get_conn_from_pool()
    if not conn or user_id is None: return None
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT id, username, password_hash, role, session_token FROM users WHERE id = %s"
        cursor.execute(query, (user_id,))
        user_data = cursor.fetchone()
        # 返回字典数据，由 user_loader 函数将其转换为 User 对象
        return user_data
    except mysql.connector.Error as err:
        print(f"获取用户失败: {err}")
        return None
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()


def verify_password(user, password):
    """验证用户输入的明文密码与数据库中的哈希密码是否匹配。"""
    if user and hasattr(user, 'password_hash'):
        return check_password_hash(user.password_hash, password)
    return False


def add_user(username, password, role='user'):
    """添加新用户。（使用原生连接）"""
    conn = get_conn_from_pool()
    if not conn: return False, "无法连接数据库。"
    cursor = None
    try:
        cursor = conn.cursor()
        password_hash = generate_password_hash(password)
        # 初始 session_token 设置为 NULL
        query = "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)"
        cursor.execute(query, (username, password_hash, role))
        conn.commit()
        return True, "用户添加成功。"
    except mysql.connector.Error as err:
        if err.errno == 1062:
            return False, "用户名已存在。"
        print(f"添加用户失败: {err}")
        return False, "数据库错误。"
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()


def get_all_users():
    """
    获取数据库中所有用户的列表 (用于管理界面)。
    """
    engine = get_sql_engine()
    if not engine: return pd.DataFrame()
    try:
        query = "SELECT id, username, role FROM users"
        df = pd.read_sql_query(query, engine)
        return df
    except Exception as err:
        # 捕获更广泛的异常，因为现在是 SQLAlchemy 错误
        print(f"获取所有用户失败: {err}")
        return pd.DataFrame()

def delete_user(user_id):
    """根据用户ID删除用户。（使用原生连接）"""
    conn = get_conn_from_pool()
    if not conn: return False, "无法连接数据库。"
    cursor = None
    try:
        cursor = conn.cursor()
        query = "DELETE FROM users WHERE id = %s"
        cursor.execute(query, (user_id,))
        conn.commit()
        if cursor.rowcount > 0:
            return True, "用户删除成功。"
        else:
            return False, "用户不存在。"
    except mysql.connector.Error as err:
        print(f"删除用户失败: {err}")
        return False, "数据库错误。"
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()


def update_user_password(user_id, new_password):
    """根据用户ID修改用户的密码。（使用原生连接）"""
    conn = get_conn_from_pool()
    if not conn:
        return False, "无法连接数据库。"
    cursor = None
    try:
        cursor = conn.cursor()
        # 1. 对新密码进行哈希处理
        password_hash = generate_password_hash(new_password)

        # 2. 执行更新操作
        query = "UPDATE users SET password_hash = %s WHERE id = %s"
        cursor.execute(query, (password_hash, user_id))
        conn.commit()

        if cursor.rowcount > 0:
            return True, "密码更新成功。"
        else:
            return False, "用户不存在，密码更新失败。"

    except mysql.connector.Error as err:
        print(f"修改用户密码失败: {err}")
        return False, "数据库错误，密码更新失败。"
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


# 生成并更新会话令牌
def update_user_session_token(user_id):
    """
    为用户生成一个新的唯一的会话令牌，并将其存储在数据库中。
    返回新的令牌。
    """
    conn = get_conn_from_pool()
    if not conn:
        return None
    cursor = None
    try:
        cursor = conn.cursor()

        # 1. 生成一个唯一的令牌 (UUID)
        new_token = str(uuid.uuid4())

        # 2. 更新数据库
        query = "UPDATE users SET session_token = %s WHERE id = %s"
        cursor.execute(query, (new_token, user_id))
        conn.commit()

        return new_token

    except mysql.connector.Error as err:
        print(f"更新用户会话令牌失败: {err}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


# 获取有效令牌
def get_user_session_token(user_id):
    """从数据库获取用户当前的有效会话令牌。"""
    conn = get_conn_from_pool()
    if not conn:
        return None
    cursor = None
    try:
        cursor = conn.cursor()
        query = "SELECT session_token FROM users WHERE id = %s"
        cursor.execute(query, (user_id,))
        result = cursor.fetchone()
        # 结果是一个元组，取第一个元素
        return result[0] if result and result[0] else None
    except mysql.connector.Error as err:
        print(f"获取用户会话令牌失败: {err}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def log_action(operator_username: str, action_type: str, target_username: str, status: str, message: str = ""):
    """
    将操作记录写入 logs 表。（使用原生连接）
    注意：您表名是 `user_logs`，而不是 `logs`，这里我已经给您修正。
    """
    conn = get_conn_from_pool()
    if not conn:
        print("[FATAL LOGGING ERROR] 无法连接数据库以记录审计日志。")
        return

    cursor = None
    try:
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor = conn.cursor()
        query = """
        INSERT INTO user_logs (timestamp, operator, action_type, target_user, status, message)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        params = (timestamp, operator_username, action_type, target_username, status, message)

        cursor.execute(query, params)
        conn.commit()

        print(
            f"[AUDIT LOG SUCCESS] {timestamp} | OP: {operator_username} | TYPE: {action_type} | TARGET: {target_username} | STATUS: {status}")

    except mysql.connector.Error as e:
        print(
            f"[FATAL LOGGING ERROR] Could not write audit log for {operator_username} -> {action_type}. MySQL Error: {e}")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

#测试案例，为了生成超级管理员，密码可以自己输入，请在生成后删除此代码
# add_user('admin','123','superadmin')
#测试案例，若往后想修改超级管理员密码，请使用下面函数
update_user_password('1','As12345678')