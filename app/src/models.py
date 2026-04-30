from sqlalchemy import Column, Integer, String, DateTime, func
from database import Base

class ApiLog(Base):
    """API実行状況ログのモデル (DB1相当)"""
    __tablename__ = "api_logs"

    id = Column(Integer, primary_key=True, index=True)
    # サーバー時刻で保存
    timestamp = Column(DateTime, default=func.now(), index=True)
    endpoint = Column(String, index=True)
    status = Column(Integer)

class MatchLog(Base):
    """在庫発見記録のモデル (DB2相当)"""
    __tablename__ = "match_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=func.now(), index=True)
    keyword = Column(String, index=True)
    title = Column(String, index=True)