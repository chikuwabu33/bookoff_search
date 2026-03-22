FROM python:3.11-slim

# 作業ディレクトリの設定
WORKDIR /app

# システムパッケージのインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Pythonパッケージのインストール
COPY requirements_frontend.txt /app/
RUN pip install --no-cache-dir -r /app/requirements_frontend.txt

# アプリケーションコードのコピー
COPY app/ /app/

# Streamlit のポート公開
EXPOSE 8501

# Streamlit フロントエンドを起動
CMD ["streamlit", "run", "src/frontend.py", "--server.port=8501", "--server.address=0.0.0.0"]
