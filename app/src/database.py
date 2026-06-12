import logging
import os

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)


def _normalize_database_url(database_url: str | None) -> str:
    """環境変数を SQLAlchemy で使える形に正規化します。"""
    if not database_url:
        data_dir = os.getenv("DATA_DIR", "./data")
        os.makedirs(data_dir, exist_ok=True)
        return f"sqlite:///{os.path.join(data_dir, 'bookoff_search.db')}"

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    if database_url.startswith("sqlite://"):
        sqlite_path = database_url[10:] if database_url.startswith("sqlite:///") else database_url[9:]
        sqlite_path = os.path.normpath(sqlite_path)
        sqlite_dir = os.path.dirname(sqlite_path) or "."
        os.makedirs(sqlite_dir, exist_ok=True)

    return database_url


def _create_engine(database_url: str):
    """SQLAlchemyエンジンを生成します。"""
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    elif database_url.startswith("postgresql"):
        connect_args = {"sslmode": "require", "connect_timeout": 10}

    engine_kwargs = {"connect_args": connect_args}
    if ":6543" in database_url:
        engine_kwargs["poolclass"] = NullPool
    else:
        engine_kwargs["pool_pre_ping"] = True

    return create_engine(database_url, **engine_kwargs)


# 環境変数からDB接続情報を取得。
# Renderなどでは外部Postgresを推奨し、未設定時はDATA_DIR下にSQLiteファイルを生成します。
DATA_DIR = os.getenv("DATA_DIR", "./data")
DATABASE_URL = _normalize_database_url(os.getenv("DATABASE_URL"))

engine = _create_engine(DATABASE_URL)

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
    """データベーステーブルを初期化（存在しない場合のみ作成）。

    Postgres 接続が失敗した場合は、ローカル SQLite へ自動フォールバックします。
    """
    global DATABASE_URL, engine, SessionLocal

    try:
        Base.metadata.create_all(bind=engine)
        return
    except Exception as exc:
        if DATABASE_URL.startswith("sqlite"):
            raise

        logger.warning(
            "データベース初期化に失敗したため、ローカル SQLite へフォールバックします: %s",
            exc,
        )

        os.makedirs(DATA_DIR, exist_ok=True)
        DATABASE_URL = f"sqlite:///{os.path.abspath(os.path.join(DATA_DIR, 'bookoff_search.db'))}"
        engine = _create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        Base.metadata.create_all(bind=engine)