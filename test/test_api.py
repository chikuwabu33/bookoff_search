"""
バックエンド API のテストスイート
pytest を使用した単体テスト・統合テスト
"""

import pytest


class TestHealth:
    """ヘルスチェックエンドポイントのテスト"""
    
    def test_health_check_success(self, client):
        """ヘルスチェック - 成功"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestStockAPI:
    """在庫確認 API (/api/stock) のテスト"""
    
    def test_stock_check_exact_match(self, client):
        """在庫確認 - 完全一致（在庫あり）"""
        response = client.post("/api/stock", json={"query": "呪術廻戦"})
        
        assert response.status_code == 200
        data = response.json()
        
        # 基本的なレスポンス構造を確認
        assert "keyword" in data
        assert "in_stock" in data
        assert "matching_count" in data
        assert "match_type" in data
        assert "products" in data
        
        # 呪術廻戦は完全一致で見つかるはず
        assert data["keyword"] == "呪術廻戦"
        assert data["in_stock"] is True
        assert data["matching_count"] > 0
        assert data["match_type"] in ["完全一致", "部分一致"]
        
        # 返された商品を確認
        if data["products"]:
            product = data["products"][0]
            assert "title" in product
            assert "price" in product
            assert "url" in product
            assert "image_url" in product
    
    def test_stock_check_partial_match(self, client):
        """在庫確認 - 部分一致（在庫あり）"""
        response = client.post("/api/stock", json={"query": "呪術"})
        
        assert response.status_code == 200
        data = response.json()
        
        # 部分一致で結果が返るはず
        assert data["keyword"] == "呪術"
        assert data["in_stock"] is True
        assert data["matching_count"] > 0
    
    def test_stock_check_not_in_stock(self, client):
        """在庫確認 - 在庫なし"""
        response = client.post("/api/stock", json={"query": "續々 さすらいエマノン"})
        
        assert response.status_code == 200
        data = response.json()
        
        # この商品は在庫がないはず
        assert data["keyword"] == "續々 さすらいエマノン"
        assert data["in_stock"] is False
        assert data["matching_count"] == 0
        assert data["match_type"] == "在庫なし"
        assert data["products"] == []
    
    def test_stock_check_empty_query(self, client):
        """在庫確認 - 空のクエリ（エラー）"""
        response = client.post("/api/stock", json={"query": ""})
        
        assert response.status_code == 400
        assert "検索クエリが入力されていません" in response.json()["detail"]
    
    def test_stock_check_whitespace_only(self, client):
        """在庫確認 - 空白のみのクエリ（エラー）"""
        response = client.post("/api/stock", json={"query": "   "})
        
        assert response.status_code == 400
        assert "検索クエリが入力されていません" in response.json()["detail"]
    
    def test_stock_check_response_structure(self, client):
        """在庫確認 - レスポンス構造の検証"""
        response = client.post("/api/stock", json={"query": "呪術廻戦"})
        
        assert response.status_code == 200
        data = response.json()
        
        # 必須フィールドの確認
        required_fields = ["keyword", "in_stock", "matching_count", "match_type", "products"]
        for field in required_fields:
            assert field in data, f"フィールド '{field}' が見つかりません"
        
        # 型の確認
        assert isinstance(data["keyword"], str)
        assert isinstance(data["in_stock"], bool)
        assert isinstance(data["matching_count"], int)
        assert isinstance(data["match_type"], str)
        assert isinstance(data["products"], list)
    
    def test_stock_check_products_limit(self, client):
        """在庫確認 - 返される商品数の制限（最大10件）"""
        response = client.post("/api/stock", json={"query": "呪術廻戦"})
        
        assert response.status_code == 200
        data = response.json()
        
        # 返される商品数は最大10件のはず
        assert len(data["products"]) <= 10


class TestSearchAPI:
    """商品検索 API (/api/search) のテスト"""
    
    def test_search_success(self, client):
        """検索 - 成功"""
        response = client.post("/api/search", json={"query": "呪術廻戦"})
        
        assert response.status_code == 200
        data = response.json()
        
        # 基本的なレスポンス構造を確認
        assert "query" in data
        assert "count" in data
        assert "results" in data
        
        # 検索結果の確認
        assert data["query"] == "呪術廻戦"
        assert data["count"] > 0
        assert len(data["results"]) > 0
        
        # 最初の商品を確認
        product = data["results"][0]
        assert "title" in product
        assert "price" in product
        assert "url" in product
        assert "image_url" in product
    
    def test_search_empty_query(self, client):
        """検索 - 空のクエリ（エラー）"""
        response = client.post("/api/search", json={"query": ""})
        
        assert response.status_code == 400
        assert "検索クエリが入力されていません" in response.json()["detail"]
    
    def test_search_response_structure(self, client):
        """検索 - レスポンス構造の検証"""
        response = client.post("/api/search", json={"query": "Python"})
        
        assert response.status_code == 200
        data = response.json()
        
        # 必須フィールドの確認
        required_fields = ["query", "count", "results"]
        for field in required_fields:
            assert field in data, f"フィールド '{field}' が見つかりません"
        
        # 型の確認
        assert isinstance(data["query"], str)
        assert isinstance(data["count"], int)
        assert isinstance(data["results"], list)


class TestAPIIntegration:
    """API 統合テスト"""
    
    def test_stock_and_search_consistency(self, client):
        """在庫確認と検索結果の一貫性"""
        keyword = "呪術廻戦"
        
        # 1. 検索を実行
        search_response = client.post("/api/search", json={"query": keyword})
        assert search_response.status_code == 200
        search_data = search_response.json()
        
        # 2. 在庫確認を実行
        stock_response = client.post("/api/stock", json={"query": keyword})
        assert stock_response.status_code == 200
        stock_data = stock_response.json()
        
        # 3. 一貫性を確認
        if search_data["count"] > 0:
            # 検索結果がある場合、在庫確認でも在庫があるはず
            assert stock_data["in_stock"] is True
    
    def test_multiple_keywords(self, client):
        """複数キーワードでの検索テスト"""
        keywords = ["呪術廻戦", "Python", "JSON"]
        
        for keyword in keywords:
            response = client.post("/api/stock", json={"query": keyword})
            assert response.status_code == 200
            data = response.json()
            assert "keyword" in data
            assert "in_stock" in data
