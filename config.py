import os

class Config:
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
    LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
    SQLITE_DB_PATH = '/tmp/lost_items.db' 
    UPLOAD_FOLDER = '/tmp/uploads'

    HUGGINGFACE_API_URL = os.getenv('HUGGINGFACE_API_URL')
    HUGGINGFACE_API_TOKEN = os.getenv('HUGGINGFACE_API_TOKEN')