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
# Hugging Face Spaces 的運行用戶通常是 UID 1000。
# 我們讓這個用戶成為這些目錄的所有者，並給予寫入權限。
# 確保 /tmp 目錄的權限，因為您的日誌顯示數據庫在 /tmp
RUN mkdir -p /app/static/uploads && chown -R 1000:0 /app/static && chmod -R 775 /app/static
RUN mkdir -p /app/data && chown -R 1000:0 /app/data && chmod -R 775 /app/data
# 由於您的數據庫在 /tmp，確保 /tmp 目錄及其內容對所有用戶可寫
RUN chmod -R 777 /tmp # 確保 /tmp 目錄及其內容對所有用戶可寫

# 聲明應用程式將監聽的埠。
# 這是 Hugging Face Spaces 預期的埠，但實際綁定由 CMD 指令控制。
EXPOSE 7860

# **僅用於診斷：執行一個簡單的 ls 命令來檢查日誌輸出**
# 如果您看到這個命令的輸出，那麼容器至少可以執行命令。
CMD ls -l /app
