FROM python:3.10-slim-buster

WORKDIR /app

COPY requirements.txt .

# 安裝所有依賴
# 使用 --no-cache-dir 禁用 pip 緩存
# 使用 --force-reinstall 強制重新安裝以避免任何現有問題
# 並將日誌級別設置為更詳細的模式
RUN pip install --no-cache-dir --force-reinstall -v -r requirements.txt

# 將所有應用程式代碼複製到工作目錄
COPY . .

# 設定環境變數 (根據您的需求可能需要調整)
ENV PYTHONUNBUFFERED=1
ENV GUNICORN_LISTEN_PORT=7860

# 建立 uploads 目錄並設定權限
# 設定 www-data 為應用程式運行用戶，確保其對 /app/static/uploads 有寫入權限
RUN mkdir -p /app/static/uploads && chown -R 1000:0 /app/static && chmod -R 775 /app/static
RUN mkdir -p /app/data && chown -R 1000:0 /app/data && chmod -R 775 /app/data # 為 db_manager 創建 /app/data

# 如果您有其他需要寫入的目錄，也要設定類似的權限
# RUN chmod -R 777 /tmp # 如果您的應用程式在 /tmp 寫入，這是必須的，但通常不推薦 777

# 暴露應用程式端口
EXPOSE 7860

# 啟動應用程式
# 使用 stdbuf -oL 確保日誌實時輸出
# 使用 --timeout 0 來禁用 Gunicorn 超時 (對於調試和長期連接有用)
CMD ["sh", "-c", "stdbuf -oL gunicorn --bind 0.0.0.0:7860 app:app --timeout 0"]
