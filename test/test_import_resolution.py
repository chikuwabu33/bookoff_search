import importlib
import sys


def test_backend_imports_work_as_src_package(monkeypatch):
    """Render での package 起動パスでも backend が import できることを確認する。"""
    project_root = __import__('pathlib').Path(__file__).resolve().parents[1]
    app_dir = project_root / 'app'

    monkeypatch.syspath_prepend(str(app_dir))
    sys.modules.pop('src.backend', None)
    sys.modules.pop('src.database', None)
    sys.modules.pop('src.models', None)

    module = importlib.import_module('src.backend')

    assert hasattr(module, 'app')
