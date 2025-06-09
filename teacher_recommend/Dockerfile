# 使用官方 Python 3.10 簡化版映像
FROM python:3.10-slim

# 設定工作目錄
WORKDIR /app

# 複製需求檔案
COPY requirements.txt .

# 安裝依賴套件（不使用 cache 以減少映像大小）
RUN pip install --no-cache-dir -r requirements.txt

# 複製整個專案內容到容器內
COPY . .

# 設定 Flask 環境變數
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=7860

# 開放端口
EXPOSE 7860

# 執行 Flask 應用程式
CMD ["flask", "run"]
