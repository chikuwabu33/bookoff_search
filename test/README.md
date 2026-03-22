# テストスイート

BOOKOFF 検索 API のため pytest を使った包括的なテストスイート

## テストの構成

```
/app/test/
├── conftest.py          # pytest 設定ファイル（TestClient の定義）
├── pytest.ini           # pytest の設定
├── test_api.py          # API テストケース
└── README.md            # このファイル
```

## テストカバレッジ

### TestHealth クラス
- ✅ ヘルスチェックエンドポイント `/health` のテスト

### TestStockAPI クラス（在庫確認 API）
- ✅ 完全一致での検索（在庫あり）
- ✅ 部分一致での検索（在庫あり）
- ✅ 在庫なしのケース
- ✅ 空のクエリエラー
- ✅ 空白のみのクエリエラー
- ✅ レスポンス構造の検証
- ✅ 返される商品数の制限（最大10件）

### TestSearchAPI クラス（商品検索 API）
- ✅ 検索成功
- ✅ 空のクエリエラー
- ✅ レスポンス構造の検証

### TestAPIIntegration クラス（統合テスト）
- ✅ 検索と在庫確認結果の一貫性
- ✅ 複数キーワードでのテスト

## テストの実行

### すべてのテストを実行

```bash
cd /app
pytest test/
```

### 詳細な出力で実行

```bash
pytest test/ -v
```

### 特定のテストクラスのみ実行

```bash
pytest test/test_api.py::TestStockAPI -v
```

### 特定のテスト関数のみ実行

```bash
pytest test/test_api.py::TestStockAPI::test_stock_check_exact_match -v
```

### カバレッジレポートを生成

```bash
pip install pytest-cov
pytest test/ --cov=app/src --cov-report=html
```

### テスト結果をサマリー表示

```bash
pytest test/ --tb=short -q
```

## セットアップ

### 必要なパッケージのインストール

```bash
pip install pytest fastapi httpx
```

### pytest-cov（カバレッジ測定）のインストール（オプション）

```bash
pip install pytest-cov
```

## テスト実行例

### 全テスト実行

```bash
$ pytest test/ -v

test/test_api.py::TestHealth::test_health_check_success PASSED
test/test_api.py::TestStockAPI::test_stock_check_exact_match PASSED
test/test_api.py::TestStockAPI::test_stock_check_partial_match PASSED
test/test_api.py::TestStockAPI::test_stock_check_not_in_stock PASSED
test/test_api.py::TestStockAPI::test_stock_check_empty_query PASSED
...

========================= 16 passed in 45.32s =========================
```

## テストのポイント

### 1. テスト分離
- 各テストは独立して実行可能
- TestClient はリクエスト時に新しいアプリケーションインスタンスを使用

### 2. アサーション
- HTTP ステータスコードの検証
- JSON レスポンスの構造検証
- フィールドの型検証
- データの妥当性検証

### 3. エラーケースのテスト
- 不正入力（空文字列、空白のみ）
- 400 Bad Request エラーハンドリング

### 4. 統合テスト
- 複数の API エンドポイント間の一貫性確認
- 実際の BOOKOFF API との連携検証

## トラブルシューティング

### ModuleNotFoundError: No module named 'backend'

`conftest.py` が `sys.path` にプロジェクトパスを正しく追加しているか確認してください。

### pytest が見つからない

```bash
pip install pytest
```

### テストが遅い

実際に BOOKOFF サイトにアクセスしているため、ネットワーク接続の速度に依存します。

## 今後の改善案

- [ ] BOOKOFF API のモック化（テスト高速化）
- [ ] より詳細なエラーメッセージテスト
- [ ] パフォーマンステスト
- [ ] 負荷テスト

## 参考資料

- [pytest 公式ドキュメント](https://docs.pytest.org/)
- [FastAPI テストド](https://fastapi.tiangolo.com/ja/advanced/testing-dependencies/)
