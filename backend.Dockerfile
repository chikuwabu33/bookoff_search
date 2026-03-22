FROM python:3.11-slim

# 作業ディレクトリの設定
WORKDIR /app

# システムパッケージのインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Pythonパッケージのインストール
COPY requirements_backend.txt /app/
RUN pip install --no-cache-dir -r /app/requirements_backend.txt

# アプリケーションコードのコピー
COPY app/ /app/

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# FastAPI サーバーのポート公開
EXPOSE 8000

# FastAPI バックエンドを起動
CMD ["python", "src/backend.py"]
