import os

class Config:
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
    LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
    SQLITE_DB_PATH = os.getenv('SQLITE_DB_PATH', 'data/lost_and_found.db') # 預設路徑

    # 本地圖片儲存路徑
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')

    HUGGINGFACE_API_URL = os.getenv('HUGGINGFACE_API_URL')
    HUGGINGFACE_API_TOKEN = os.getenv('HUGGINGFACE_API_TOKEN')