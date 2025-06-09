import sqlite3
import os
from enum import Enum
from datetime import datetime 

class UserState(Enum):
    NONE = "none" 
    REPORTING_START = "reporting_start" 
    REPORTING_WAIT_IMAGE = "reporting_wait_image" 
    REPORTING_WAIT_DESCRIPTION = "reporting_wait_description" 
    REPORTING_WAIT_LOCATION = "reporting_wait_location" 
    
class DBManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self._ensure_db_dir_exists()
        self._create_tables()

    def _ensure_db_dir_exists(self):
        db_dir = os.path.dirname(self.db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _create_tables(self):
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_states (
                user_id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                current_item_id TEXT 
            )
        ''')

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
        conn.commit()
        conn.close()

    def get_user_state(self, user_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT state, current_item_id FROM user_states WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        if result:
            return UserState(result[0]), result[1]
        return UserState.NONE, None 

    def update_user_state(self, user_id, new_state, current_item_id=None):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO user_states (user_id, state, current_item_id) VALUES (?, ?, ?)",
                       (user_id, new_state.value, current_item_id))
        conn.commit()
        conn.close()

    def clear_user_state(self, user_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

    def create_new_lost_item(self, user_id):
        import uuid
        item_id = str(uuid.uuid4())
        report_date = datetime.now().isoformat()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO lost_items (item_id, user_id, report_date) VALUES (?, ?, ?)",
                       (item_id, user_id, report_date))
        conn.commit()
        conn.close()
        return item_id

    def save_item_image_url(self, item_id, image_url): 
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE lost_items SET image_url = ? WHERE item_id = ?", (image_url, item_id))
        conn.commit()
        conn.close()

    def save_item_description(self, item_id, description):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE lost_items SET description = ? WHERE item_id = ?", (description, item_id))
        conn.commit()
        conn.close()

    def save_item_location(self, item_id, location):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE lost_items SET location = ? WHERE item_id = ?", (location, item_id))
        conn.commit()
        conn.close()

    def retrieve_lost_items(self, resolved=False):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT item_id, user_id, image_url, description, location, report_date FROM lost_items WHERE is_resolved = ? ORDER BY report_date DESC", (resolved,))
        items = []
        for row in cursor.fetchall():
            items.append({
                "item_id": row[0],
                "user_id": row[1],
                "image_url": row[2],
                "description": row[3],
                "location": row[4],
                "report_date": row[5]
            })
        conn.close()
        return items