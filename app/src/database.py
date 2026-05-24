import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import event

# 環境変数からDB接続情報を取得。デフォルトはローカルSQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/bookoff_search.db")

# RenderやSupabaseなどの環境で "postgres://" となっている場合に "postgresql://" に変換する
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Supabaseのコネクションプーラー (ポート 6543) を使用する場合の対応
# トランザクションモードでは prepared statements を無効にする必要がある
if ":6543" in DATABASE_URL and "prepared_statements" not in DATABASE_URL:
    separator = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL += f"{separator}prepared_statements=false"

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

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args
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