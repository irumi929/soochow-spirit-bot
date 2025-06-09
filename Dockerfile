FROM python:3.10-slim

# 安裝系統依賴
RUN apt-get update && apt-get install -y git git-lfs ffmpeg libsm6 libxext6 cmake rsync libgl1-mesa-glx build-essential libffi-dev libssl-dev && rm -rf /var/lib/apt/lists/* && git lfs install

# 設定工作目錄
WORKDIR /app

# 複製 requirements.txt 並安裝 Python 依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- 新增這兩行來強制後續層不使用快取 ---
# 這一層每次都會變化，因為時間戳不同，從而使後續的層快取失效
RUN echo $(date +%s) > /tmp/cache_buster_timestamp && cat /tmp/cache_buster_timestamp

# 複製應用程式程式碼 (現在這一層肯定會被重新執行)
COPY . .

# 創建並設置靜態文件和數據庫文件夾的權限
RUN mkdir -p /app/static/uploads && chown -R 1000:0 /app/static && chmod -R 775 /app/static
RUN mkdir -p /app/data && chown -R 1000:0 /app/data && chmod -R 775 /app/data
RUN chmod -R 777 /tmp # 確保 /tmp 目錄及其內容對所有用戶可寫

# 聲明應用程式將監聽的埠
EXPOSE 7860

# 定義容器啟動時運行的命令。
# 使用 `||` (OR) 操作符：如果 Gunicorn 成功啟動，則後面的循環不會執行。
# 如果 Gunicorn 啟動失敗，則 `||` 後面的命令會執行，進入一個無限循環並持續輸出日誌。
CMD sh -c "echo 'Attempting Gunicorn startup...' && \
           stdbuf -oL gunicorn --worker-class gthread --workers 1 --timeout 120 --bind \"0.0.0.0:${PORT:-7860}\" app:app || \
           (echo 'Gunicorn failed to start. Entering infinite loop for debugging.' && \
            while true; do \
                echo 'Container is alive but Gunicorn failed. Check previous logs for errors or configuration.' && \
                sleep 10; \
            done)"