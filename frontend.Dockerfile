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
COPY requirements_frontend.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements_frontend.txt

# アプリケーションコードのコピー
COPY --chown=appuser:appuser app/ .

# データ保存用ディレクトリの作成と、/app全体の所有権をappuserに一括設定
RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

# ヘルスチェック (Streamlit専用エンドポイント)
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Streamlit のポート公開
EXPOSE 8501

# Streamlit フロントエンドを起動
CMD ["streamlit", "run", "src/frontend.py", "--server.port=8501", "--server.address=0.0.0.0"]
