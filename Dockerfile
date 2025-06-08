FROM python:3.10-slim

# 安裝系統依賴 (從您之前的日誌複製過來，確保完整性)
RUN apt-get update && \
    apt-get install -y git git-lfs ffmpeg libsm6 libxext6 cmake rsync libgl1-mesa-glx && \
    rm -rf /var/lib/apt/lists/* && \
    git lfs install

# 設定工作目錄
WORKDIR /app

# 複製 requirements.txt 並安裝依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製所有應用程式程式碼
COPY . .

# 創建並設置靜態文件和數據庫文件夾的權限
RUN mkdir -p /app/static/uploads && chown -R 1000:0 /app/static && chmod -R 775 /app/static
RUN mkdir -p /app/data && chown -R 1000:0 /app/data && chmod -R 775 /app/data
RUN chmod -R 777 /tmp # 確保 /tmp 目錄及其內容對所有用戶可寫

# 聲明應用程式將監聽的埠。
EXPOSE 7860

# **僅用於診斷：檢查 gunicorn 可執行性**
# 執行一個簡單的 echo 命令，然後嘗試執行 `which gunicorn` 和 `gunicorn --version`。
# 如果這些命令都無法產生日誌，那問題可能非常底層。
CMD sh -c "echo '--- Starting Gunicorn Executable Check ---' && \
           which gunicorn && \
           gunicorn --version && \
           echo '--- Gunicorn Check Complete ---' && \
           sleep 30" # 讓容器保持運行一段時間，以便捕獲日誌
