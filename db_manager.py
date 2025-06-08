import sqlite3
import os
from enum import Enum
from datetime import datetime
import logging # 新增導入

# 配置 logging (確保在導入 DBManager 前 app.py 也有配置，或者直接在這裡配置)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# 定義用戶狀態的枚舉
class UserState(Enum):
    NONE = "none" # 初始狀態，沒有特定流程
    REPORTING_START = "reporting_start" # 開始上報失物
    REPORTING_WAIT_IMAGE = "reporting_wait_image" # 等待用戶上傳圖片
    REPORTING_WAIT_DESCRIPTION = "reporting_wait_description" # 等待用戶輸入描述
    REPORTING_WAIT_LOCATION = "reporting_wait_location" # 等待用戶輸入位置

class DBManager:
    def __init__(self, db_path):
        self.db_path = db_path
        logging.info(f"DBManager: Initializing with db_path: {self.db_path}") # 新增日誌

        try:
            self._ensure_db_dir_exists()
            logging.info("DBManager: Database directory ensured.") # 新增日誌
        except Exception as e:
            logging.error(f"DBManager ERROR: Failed to ensure database directory exists: {e}", exc_info=True) # 捕獲並打印錯誤
            raise # 重新拋出異常，讓應用程式崩潰並顯示此錯誤

        try:
            self._create_tables()
            logging.info("DBManager: Tables created/verified successfully.") # 新增日誌
        except Exception as e:
            logging.error(f"DBManager ERROR: Failed to create/verify tables: {e}", exc_info=True) # 捕獲並打印錯誤
            raise # 重新拋出異常，讓應用程式崩潰並顯示此錯誤

    def _ensure_db_dir_exists(self):
        db_dir = os.path.dirname(self.db_path)
        logging.info(f"DBManager: Checking/creating directory: {db_dir}") # 新增日誌
        if not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir)
                logging.info(f"DBManager: Successfully created directory: {db_dir}") # 新增日誌
            except OSError as e:
                logging.error(f"DBManager ERROR: os.makedirs failed for {db_dir}: {e}", exc_info=True) # 捕獲並打印錯誤
                raise # 重新拋出 OSError

    def _get_connection(self):
        try:
            conn = sqlite3.connect(self.db_path)
            logging.info(f"DBManager: Connected to database: {self.db_path}") # 新增日誌
            return conn
        except sqlite3.Error as e:
            logging.error(f"DBManager ERROR: Failed to connect to database {self.db_path}: {e}", exc_info=True) # 捕獲並打印錯誤
            raise # 重新拋出 SQLite 錯誤

    def _create_tables(self):
        conn = None # 確保 conn 在 finally 中被關閉
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_states (
                    user_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    current_item_id TEXT
                )
            ''')
            logging.info("DBManager: 'user_states' table check/creation SQL executed.")

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS lost_items (
                    item_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    image_url TEXT,
                    description TEXT,
                    location TEXT,
                    report_date TEXT NOT NULL,
                    is_resolved BOOLEAN DEFAULT FALSE
                )
            ''')
            logging.info("DBManager: 'lost_items' table check/creation SQL executed.")
            conn.commit()
            logging.info("DBManager: Database commit successful.")
        except sqlite3.Error as e:
            logging.error(f"DBManager ERROR: Failed to create/verify tables: {e}", exc_info=True)
            raise
        finally:
            if conn:
                conn.close()
                logging.info("DBManager: Database connection closed after table creation.")

    # ... (其他方法保持不變)