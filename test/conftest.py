"""
pytest の設定ファイル
FastAPI テスト用の共通設定
"""

import pytest
import sys
from pathlib import Path

# プロジェクトのルートパスを sys.path に追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "app" / "src"))

# テストクライアント
from fastapi import FastAPI
from starlette.testclient import TestClient


# FastAPI アプリをロード
from backend import app as fastapi_app


@pytest.fixture
def app():
    """FastAPI アプリケーション フィクスチャ"""
    return fastapi_app


@pytest.fixture
def client(app):
    """テストクライアント フィクスチャ"""
    return TestClient(app, raise_server_exceptions=False)
