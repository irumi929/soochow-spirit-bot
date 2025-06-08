FROM python:3.10-slim

# 安裝系統依賴 (從您之前的日誌複製過來，確保完整性)
RUN apt-get update && apt-get install -y 	git 	git-lfs 	ffmpeg 	libsm6 	libxext6 	cmake 	rsync 	libgl1-mesa-glx 	&& rm -rf /var/lib/apt/lists/* && git lfs install

# 如果 Hugging Face Spaces 的 Docker SDK 沒有自動創建用戶，您可能需要這些行
# RUN useradd -m -u 1000 user
# USER 1000 # 切換到非 root 用戶運行

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 確保在複製應用程式碼之後，設置權限
COPY . .

# 創建並設置靜態文件和數據庫文件夾的權限
# Hugging Face Spaces 的運行用戶通常是 UID 1000。
# 我們讓這個用戶成為這些目錄的所有者，並給予寫入權限。
RUN mkdir -p /app/static/uploads && chown -R 1000:0 /app/static
RUN mkdir -p /app/data && chown -R 1000:0 /app/data
RUN chmod -R 775 /app/static /app/data # 給予所有者和組讀寫執行權限

EXPOSE 8000
# 嘗試使用舊的 IPv4 任何地址，雖然您已在使用，但重寫一次確保
CMD ["gunicorn", "--worker-class", "gthread", "--workers", "1", "--timeout", "120", "--bind", "0:8000", "app:app"]
EXPOSE 7860
