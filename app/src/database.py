import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 環境変数からDB接続情報を取得。デフォルトはローカルSQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/bookoff_search.db")

# RenderやSupabaseなどの環境で "postgres://" となっている場合に "postgresql://" に変換する
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLAlchemyエンジンの作成
connect_args = {}
# SQLiteを使用する場合のみ、スレッド間での同一接続許可設定が必要
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args
)

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