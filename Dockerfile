# 使用官方 Python 映像檔
FROM python:3.11-slim

# 設定環境變數，防止 Python 寫入 .pyc 文件
ENV PYTHONDONTWRITEBYTECODE 1
# 設定 Python 輸出為非緩衝，以便日誌直接顯示
ENV PYTHONUNBUFFERED 1

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴項 (如果 matplotlib 需要)
# matplotlib 可能需要一些字體或後端支持，這裡先安裝常用的 fontconfig
# 如果遇到字體問題，可能需要安裝更多字體包
RUN apt-get update && apt-get install -y --no-install-recommends \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# 複製 requirements 文件並安裝依賴項
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程式碼
COPY main.py main.py

# 設定容器啟動時執行的命令
# 環境變數 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID 需要在 docker run 時傳入
CMD ["python", "main.py"] 