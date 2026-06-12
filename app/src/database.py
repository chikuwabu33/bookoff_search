import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import event
from sqlalchemy.pool import NullPool

# 環境変数からDB接続情報を取得。
# Renderなどでは外部Postgresを推奨し、未設定時はDATA_DIR下にSQLiteファイルを生成します。
DATA_DIR = os.getenv("DATA_DIR", "./data")
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    os.makedirs(DATA_DIR, exist_ok=True)
    DATABASE_URL = f"sqlite:///{os.path.join(DATA_DIR, 'bookoff_search.db')}"
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
elif DATABASE_URL.startswith("sqlite://"):
    # SQLite利用時はファイルのディレクトリを事前に作成
    sqlite_path = DATABASE_URL[10:] if DATABASE_URL.startswith("sqlite:///" ) else DATABASE_URL[9:]
    sqlite_path = os.path.normpath(sqlite_path)
    sqlite_dir = os.path.dirname(sqlite_path) or "."
    os.makedirs(sqlite_dir, exist_ok=True)

# SQLAlchemyエンジンの作成
connect_args = {}
# SQLiteを使用する場合のみ、スレッド間での同一接続許可設定が必要
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
elif DATABASE_URL.startswith("postgresql"):
    # リモートPostgres接続時にSSLを強制
    # connect_args ではなく URL パラメータで指定することが推奨される場合もありますが
    # ここでは既存のロジックを維持しつつ安定性を高めます
    connect_args = {"sslmode": "require", "connect_timeout": 10}

# Supabaseのコネクションプーラー (ポート 6543) 使用時は NullPool を使用して
# SQLAlchemy 側のプーリングを無効化し、プーラー側での管理に任せるのが安全です
engine_kwargs = {"connect_args": connect_args}
if ":6543" in DATABASE_URL:
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs["pool_pre_ping"] = True

engine = create_engine(
    DATABASE_URL,
    **engine_kwargs
)

# SQLiteのパフォーマンスと並行性を向上させる設定
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# セッション作成用のクラス
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# モデル定義のベースクラス
Base = declarative_base()

def get_db():
    """APIリクエストごとにDBセッションを生成・クローズする依存用関数"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db_tables():
    """データベーステーブルを初期化（存在しない場合のみ作成）"""
    Base.metadata.create_all(bind=engine)