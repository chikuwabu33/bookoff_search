from sqlalchemy import Column, Integer, String, DateTime
from database import Base
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

def get_jst_now():
    return datetime.now(JST).replace(tzinfo=None)

class ApiLog(Base):
    """API実行状況ログのモデル (DB1相当)"""
    __tablename__ = "api_logs"

    id = Column(Integer, primary_key=True, index=True)
    # JST時刻で保存
    timestamp = Column(DateTime, default=get_jst_now, index=True)
    endpoint = Column(String, index=True)
    status = Column(Integer)

class MatchLog(Base):
    """在庫発見記録のモデル (DB2相当)"""
    __tablename__ = "match_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=get_jst_now, index=True)
    keyword = Column(String, index=True)
    title = Column(String, index=True)