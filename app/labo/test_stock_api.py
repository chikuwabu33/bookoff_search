"""
在庫確認API (/api/stock) のテストスクリプト
"""

import requests
import json

BASE_URL = "http://localhost:8000"


def test_stock_check(keyword):
    """在庫確認APIをテスト"""
    print("\n" + "="*60)
    print(f"在庫確認テスト: '{keyword}'")
    print("="*60)
    
    try:
        payload = {"query": keyword}
        response = requests.post(
            f"{BASE_URL}/api/stock",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n[OK] リクエスト成功")
            print(f"  キーワード: {result['keyword']}")
            print(f"  在庫状況: {'あり' if result['in_stock'] else 'なし'}")
            print(f"  マッチタイプ: {result['match_type']}")
            print(f"  マッチ件数: {result['matching_count']}")
            
            if result['products']:
                print(f"\n【該当商品】（最大10件）:")
                for idx, product in enumerate(result['products'], 1):
                    print(f"  {idx}. {product['title'][:50]}")
                    print(f"     価格: {product['price']}")
                    print()
        else:
            print(f"[NG] エラー: {response.status_code}")
            print(f"  {response.text}")
            
    except requests.exceptions.ConnectionError:
        print(f"[NG] サーバーに接続できません: {BASE_URL}")
        print("    backend.py が起動していることを確認してください")
    except Exception as e:
        print(f"[ERROR] {str(e)}")


def main():
    """メイン処理"""
    print("========================================")
    print("在庫確認API テストツール")
    print("========================================")
    
    keywords = [
        "呪術廻戦",
        "續々 さすらいエマノン",
        "Python"
    ]
    
    for keyword in keywords:
        test_stock_check(keyword)


if __name__ == "__main__":
    main()
