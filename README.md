# BOOKOFF検索アプリケーション

BOOKOFF オンラインストア (https://shopping.bookoff.co.jp/) の検索機能を提供するWebアプリケーションです。

## 機能

- **設定不要な検索**: キーワードでBOOKOFFの商品を検索
- **リアルタイム結果**: 検索結果をリアルタイムで表示
- **ユーザーフレンドリーなUI**: Streamlitによる直感的なインターフェース
- **API ベース**: FastAPIによる拡張可能なバックエンド

## アーキテクチャ

```
┌──────────────────────────────────────────────┐
│         Docker Compose (複数コンテナ)        │
├──────────────────────────────────────────────┤
│                                              │
│  ┌──────────────────┐  ┌──────────────────┐ │
│  │  Backend        │  │  Frontend        │ │
│  │  Container      │  │  Container       │ │
│  ├──────────────────┤  ├──────────────────┤ │
│  │  FastAPI        │  │  Streamlit       │ │
│  │  (Port 8000)    │  │  (Port 8501)     │ │
│  └─────────┬────────┘  └────────┬─────────┘ │
│            │                    │           │
│            └────────┬───────────┘           │
│                     │                       │
│            ┌────────▼────────┐             │
│            │  BOOKOFF サイト  │             │
│            └─────────────────┘             │
│                                              │
│  ネットワーク: bookoff-network              │
└──────────────────────────────────────────────┘
```

### ファイル構成

```
docker-template/
├── backend.Dockerfile       # FastAPI バックエンド用
├── frontend.Dockerfile      # Streamlit フロントエンド用
├── docker-compose.yml       # Docker Compose 設定（複数コンテナ定義）
├── requirements.txt         # Python 依存パッケージ
├── README.md               # このファイル
└── app/
    ├── backend.py          # FastAPI バックエンド
    └── frontend.py         # Streamlit フロントエンド
```

## 必要なソフトウェア

- Docker Desktop (Windows/Mac) または Docker + Docker Compose (Linux)

## クイックスタート

### docker compose で起動

```bash
# コンテナをビルド・起動
docker compose up --build

# バックグラウンドで起動
docker compose up -d

# ログを表示
docker compose logs -f

# コンテナを停止
docker compose down
```

## アクセス方法

アプリケーション起動後、以下のURLでアクセス可能です：

- **Streamlit アプリ**: http://localhost:8501
- **FastAPI ドキュメント**: http://localhost:8000/docs
- **ヘルスチェック**: http://localhost:8000/health

## 使用方法

1. Streamlit アプリ (http://localhost:8501) にアクセス
2. 左側のサイドバーに検索キーワードを入力
3. 「🔍 検索」ボタンをクリック
4. 検索結果が表示されます
5. 「詳細を見る」リンクをクリックしてBOOKOFF公式サイトを確認

## API エンドポイント

### Health Check
```
GET /health
```

レスポンス:
```json
{"status": "healthy"}
```

### 検索
```
POST /api/search
```

リクエストボディ:
```json
{
  "query": "検索キーワード"
}
```

レスポンス:
```json
{
  "query": "検索キーワード",
  "count": 5,
  "results": [
    {
      "title": "商品タイトル",
      "price": "¥1,000",
      "url": "https://shopping.bookoff.co.jp/products/...",
      "image_url": "https://..."
    }
  ]
}
```

## トラブルシューティング

### FastAPIサーバーに接続できない

```bash
# ログを確認
docker-compose logs app

# コンテナを再起動
docker-compose restart
```

### Streamlit がバックエンドに接続できない

```bash
# コンテナのネットワークを確認
docker network ls
docker inspect bookoff-network

# バックエンドが正常に起動しているか確認
docker logs bookoff-backend
```

コンテナ間通信では `localhost` ではなく **コンテナ名** (`backend`) を使用してください。

## ログ確認

```bash
# リアルタイムログの表示
docker-compose logs -f app
```

## Dev Container での開発

VS Code Dev Container を使用して、バックエンドのみの環境で開発・テストできます。

### セットアップ

1. VS Code で このプロジェクトフォルダを開く
2. コマンドパレット (`Ctrl+Shift+P`) で `Dev Containers: Reopen in Container` を実行
3. バックエンド (`backend`) サービスのみがDocker内で起動します
4. VS Code のターミナルで開発・テストが可能

### Dev Container 内での操作

```bash
# バックエンドサーバーを起動
python backend.py

# 環境テスト（別のターミナル）
python test_backend_logic.py

# 検証スクリプト実行
python verify_bookoff.py
python analyze_html_detail.py
```

**注**: Dev Container では **バックエンドのみ** が起動します。フロントエンド（Streamlit）は起動しません。

---

## 開発

### ローカルでの実行（Dockerを使わない）

```bash
# 依存パッケージのインストール
pip install -r requirements.txt

# FastAPI バックエンド
python app/backend.py

# Streamlit フロントエンド（異なるターミナル）
streamlit run app/frontend.py
```

## テクノロジー

- **フロントエンド**: Streamlit 1.28.1
- **バックエンド**: FastAPI 0.104.1
- **スクレイピング**: BeautifulSoup4, Requests
- **コンテナ**: Docker, Docker Compose
- **Python**: 3.11

## プロジェクト構成

```
docker-template/
├── .devcontainer/
│   └── devcontainer.json       # VS Code Dev Container設定
├── app/
│   └── app.py                  # Flaskアプリケーション
├── .dockerignore               # Dockerビルド除外リスト
├── docker-compose.yml          # Docker Compose設定
├── Dockerfile                  # Dockerイメージ定義
├── requirements.txt            # Python依存パッケージ
└── README.md                   # このファイル
```

## カスタマイズ

### Pythonバージョンの変更

`Dockerfile`の最初の行を変更：

```dockerfile
FROM python:3.10-slim  # 3.10に変更
```

### 追加パッケージのインストール

`requirements.txt`に追加：

```
numpy==1.24.0
pandas==2.0.0
```

その後、再度コンテナをビルド：

```bash
docker-compose up --build
```

### ポート番号の変更

`docker-compose.yml`を編集：

```yaml
ports:
  - "9000:8000"  # ホスト:コンテナ
```

### データベースの有効化

`docker-compose.yml`のPostgreSQL設定をコメント解除してください。

## 開発コマンド

コンテナ内での操作：

```bash
# アプリケーション実行
python app.py

# テスト実行
pytest

# コード品質チェック
black app/
flake8 app/
pylint app/

# インタラクティブシェル
python
```

## ベストプラクティス

1. **環境変数の管理**: `.env`ファイルを作成して機密情報を管理
2. **マルチステージビルド**: 本番環境用に`Dockerfile`を最適化
3. **ヘルスチェック**: 本番環境でのコンテナ監視に活用
4. **ログレベル**: `DEBUG=False`を本番環境で設定

## トラブルシューティング

### ポート既に使用中

```bash
# ポート確認
netstat -ano | findstr :8000  # Windows
lsof -i :8000  # Mac/Linux

# 別のポートで起動
docker-compose up -p my_app
```

### 権限エラー

Linux/Macでの権限問題：

```bash
sudo usermod -aG docker $USER
```

### キャッシュをクリア

```bash
docker-compose down
docker system prune -a
docker-compose up --build
```

## 参考資料

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [VS Code Dev Containers](https://code.visualstudio.com/docs/devcontainers/containers)
- [Flask Documentation](https://flask.palletsprojects.com/)

## ライセンス

MIT License
