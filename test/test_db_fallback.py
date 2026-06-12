import importlib

import sqlalchemy.exc


def test_init_db_tables_falls_back_to_sqlite_on_operational_error(monkeypatch, tmp_path):
    """DB 初期化時に接続失敗した場合、ローカル SQLite へフォールバックする。"""
    db = importlib.import_module('database')

    calls = {'count': 0}
    original_create_all = db.Base.metadata.create_all

    def fake_create_all(bind=None):
        calls['count'] += 1
        if calls['count'] == 1:
            raise sqlalchemy.exc.OperationalError('conn', None, Exception('tenant/user not found'))
        return original_create_all(bind=bind)

    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:pass@host:6543/db')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setattr(db, 'DATABASE_URL', 'postgresql://user:pass@host:6543/db')
    monkeypatch.setattr(db, 'DATA_DIR', str(tmp_path))
    monkeypatch.setattr(db, 'engine', db._create_engine('postgresql://user:pass@host:6543/db'))
    monkeypatch.setattr(db.Base.metadata, 'create_all', fake_create_all)

    db.init_db_tables()

    assert calls['count'] == 2
    assert db.DATABASE_URL.startswith('sqlite:///')
    assert 'bookoff_search.db' in db.DATABASE_URL
