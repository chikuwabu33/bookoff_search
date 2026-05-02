FROM python:3.12-slim

# Pythonの動作設定
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 作業ディレクトリの設定
WORKDIR /app

# システムパッケージのインストールとユーザーの作成
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser \
    && useradd -r -g appuser -m -d /home/appuser appuser

# Pythonパッケージのインストール
COPY requirements_backend.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements_backend.txt

# Playwrightのシステム依存関係をrootユーザーでインストール
RUN playwright install-deps chromium

# Playwrightブラウザのインストール先とデータディレクトリの準備
ENV HOME=/home/appuser
ENV PLAYWRIGHT_BROWSERS_PATH=/home/appuser/.cache/ms-playwright

# アプリケーションコードのコピー
COPY --chown=appuser:appuser app/ .

# Playwrightのキャッシュとデータディレクトリを準備し、/app全体の所有権をappuserに一括設定
RUN mkdir -p /home/appuser/.cache/ms-playwright /app/data && \
    chown -R appuser:appuser /home/appuser /app

USER appuser
RUN python -m playwright install chromium

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# FastAPI サーバーのポート公開
EXPOSE 8000

# FastAPI バックエンドを起動
CMD ["python", "src/backend.py"]
