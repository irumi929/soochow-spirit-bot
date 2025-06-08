FROM python:3.10-slim

# 安裝系統依賴，特別新增 `build-essential`, `libffi-dev`, `libssl-dev`
RUN apt-get update && \
    apt-get install -y git git-lfs ffmpeg libsm6 libxext6 cmake rsync libgl1-mesa-glx \
                       build-essential libffi-dev libssl-dev && \ # <-- 新增這些關鍵依賴
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

# 定義容器啟動時運行的命令。
# 這次直接嘗試啟動 Gunicorn，因為我們預期依賴問題已解決。
CMD gunicorn --worker-class gthread --workers 1 --timeout 120 --bind "0.0.0.0:${PORT:-7860}" app:app
