"""
BOOKOFF 検索機能の検証スクリプト
実際にBOOKOFFサイトにアクセスして、HTMLの構造を確認し、
検索ロジックが正しく動作するかをテストします。
"""

import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urlencode
import time


class BOOKOFFValidator:
    """BOOKOFF検索機能の検証クラス"""
    
    def __init__(self):
        self.base_url = "https://shopping.bookoff.co.jp"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    
    def test_connectivity(self):
        """BOOKOFF サイトへのアクセス確認"""
        print("\n" + "="*60)
        print("1. BOOKOFF サイトへのアクセステスト")
        print("="*60)
        try:
            response = requests.head(self.base_url, headers=self.headers, timeout=10)
            print(f"[OK] アクセス成功: ステータスコード {response.status_code}")
            return True
        except Exception as e:
            print(f"[NG] アクセス失敗: {str(e)}")
            return False
    
    def test_search_request(self, keyword="Python"):
        """検索リクエストのテスト"""
        print("\n" + "="*60)
        print(f"2. 検索リクエストテスト (キーワード: '{keyword}')")
        print("="*60)
        
        search_url = f"{self.base_url}/search?keyword={keyword}"
        print(f"URL: {search_url}")
        
        try:
            response = requests.get(search_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            print(f"[OK] 検索リクエスト成功: ステータスコード {response.status_code}")
            print(f"    コンテンツサイズ: {len(response.content)} bytes")
            return response
        except Exception as e:
            print(f"[NG] 検索リクエスト失敗: {str(e)}")
            return None
    
    def analyze_html_structure(self, html_content):
        """HTML構造の解析"""
        print("\n" + "="*60)
        print("3. HTML構造の解析")
        print("="*60)
        
        soup = BeautifulSoup(html_content, "lxml")
        
        # ページタイトルを確認
        title = soup.find("title")
        print(f"ページタイトル: {title.get_text() if title else '不明'}")
        
        # すべてのdivクラスを列挙（最初の50個）
        print("\n[DIV] 検出された div クラス (最初の20個):")
        div_classes = {}
        for div in soup.find_all("div", limit=100):
            class_attr = div.get("class")
            if class_attr:
                class_name = " ".join(class_attr)
                div_classes[class_name] = div_classes.get(class_name, 0) + 1
        
        for class_name, count in sorted(div_classes.items(), key=lambda x: x[1], reverse=True)[:20]:
            print(f"    - {class_name}: {count}")
        
        # すべてのアンカータグのクラスを列挙
        print("\n[LINK] 検出されたアンカータグクラス (最初の15個):")
        link_classes = {}
        for link in soup.find_all("a", limit=100):
            class_attr = link.get("class")
            if class_attr:
                class_name = " ".join(class_attr)
                link_classes[class_name] = link_classes.get(class_name, 0) + 1
        
        for class_name, count in sorted(link_classes.items(), key=lambda x: x[1], reverse=True)[:15]:
            print(f"    - {class_name}: {count}")
        
        # スパンタグのクラスを列挙
        print("\n[SPAN] 検出された span クラス (最初の15個):")
        span_classes = {}
        for span in soup.find_all("span", limit=100):
            class_attr = span.get("class")
            if class_attr:
                class_name = " ".join(class_attr)
                span_classes[class_name] = span_classes.get(class_name, 0) + 1
        
        for class_name, count in sorted(span_classes.items(), key=lambda x: x[1], reverse=True)[:15]:
            print(f"    - {class_name}: {count}")
        
        return soup
    
    def extract_products(self, soup):
        """商品情報の抽出"""
        print("\n" + "="*60)
        print("4. 商品情報の抽出")
        print("="*60)
        
        results = []
        
        # productItem クラスを持つ div を取得
        items = soup.find_all("div", class_="productItem")
        
        if not items:
            print("[NG] productItem要素が見つかりません")
            return results
        
        print(f"[OK] productItem 要素を検出: {len(items)} 個")
        print(f"\n検査対象: {len(items)} 個のアイテム\n")
        
        for idx, item in enumerate(items[:20], 1):  # 最初の20個をテスト
            try:
                # タイトル抽出（正確なセレクタを使用）
                title_elem = item.find("p", class_="productItem__title")
                title = title_elem.get_text(strip=True) if title_elem else ""
                
                if not title:
                    continue
                
                # 価格抽出（正確なセレクタを使用）
                price_elem = item.find("p", class_="productItem__price")
                price = price_elem.get_text(strip=True) if price_elem else "価格不明"
                
                # URL抽出
                url_elem = item.find("a", class_="productItem__link") or item.find("a", class_="productItem__image")
                url = url_elem.get("href", "") if url_elem else ""
                
                # 相対URLの場合は絶対URLに変換
                if url and not url.startswith("http"):
                    url = self.base_url + url
                
                # 画像抽出
                img_elem = item.find("img")
                image_url = img_elem.get("src", "") if img_elem else ""
                
                if title and url:
                    result = {
                        "title": title[:60] + "..." if len(title) > 60 else title,
                        "price": price,
                        "url": url,
                        "image_url": image_url[:80] + "..." if len(image_url) > 80 else image_url
                    }
                    results.append(result)
                    print(f"商品 {len(results)}:")
                    print(f"  タイトル: {result['title']}")
                    print(f"  価格: {result['price']}")
                    print(f"  URL: {result['url']}")
                    if image_url:
                        print(f"  画像: {result['image_url']}")
                    print()
            
            except Exception as e:
                print(f"[WARN] アイテム {idx} の処理エラー: {str(e)}")
                continue
        
        return results
    
    def validate_search(self, keyword="Python"):
        """完全な検索プロセスの検証"""
        print("\n" + "="*60)
        print("[TEST] BOOKOFF 検索機能の検証を開始します")
        print("="*60)
        
        # 1. 接続テスト
        if not self.test_connectivity():
            print("\n[NG] サイトにアクセスできません。インターネット接続を確認してください。")
            return False
        
        # 2. 検索リクエスト
        response = self.test_search_request(keyword)
        if not response:
            print("\n[NG] 検索リクエストに失敗しました。")
            return False
        
        # アクセス遅延（サーバーへの負荷軽減）
        print("\n[WAIT] 次のリクエストまで待機中... (3秒)")
        time.sleep(3)
        
        # 3. HTML構造の解析
        soup = self.analyze_html_structure(response.content)
        
        # 4. 商品情報の抽出
        results = self.extract_products(soup)
        
        # 5. 結果のサマリー
        print("\n" + "="*60)
        print("5. 検証結果のサマリー")
        print("="*60)
        
        if results:
            # キーワードを単語で分割して検索
            keywords_parts = keyword.split()
            
            # 完全一致：全てのキーワード部分を含む商品
            fully_matching = [
                r for r in results 
                if all(part in r['title'] for part in keywords_parts if part)
            ]
            
            # 部分一致：いずれかのキーワード部分を含む商品
            partial_matching = [
                r for r in results 
                if any(part in r['title'] for part in keywords_parts if part)
            ]
            
            if fully_matching:
                print(f"\n[OK] 完全一致: {len(fully_matching)} 件の『{keyword}』を抽出しました")
                print("\n【完全一致商品】")
                for idx, result in enumerate(fully_matching, 1):
                    print(f"  {idx}. {result['title']}")
                    print(f"     価格: {result['price']}")
                    print(f"     URL: {result['url']}\n")
                return True
            elif partial_matching:
                print(f"\n[OK] 部分一致: {len(partial_matching)} 件の【関連商品】を抽出しました")
                print(f"    (完全一致はありませんが、キーワードの一部を含む商品が見つかりました)")
                print("\n【部分一致商品】")
                for idx, result in enumerate(partial_matching, 1):
                    print(f"  {idx}. {result['title']}")
                    print(f"     価格: {result['price']}")
                    print(f"     URL: {result['url']}\n")
                    if idx >= 5:
                        if len(partial_matching) > 5:
                            print(f"  ... ほか {len(partial_matching) - 5} 件\n")
                        break
                return True
            else:
                print(f"\n[NG] 『{keyword}』は在庫がありません")
                return False
        else:
            print("\n[WARN] 商品を抽出できませんでした")
            print("      - HTML 構造が変更されている可能性があります")
            print("      - クラス名を上記の結果に基づいて更新してください")
            return False


def main():
    """メイン処理"""
    validator = BOOKOFFValidator()
    
    # テスト用キーワード
    #keywords = ["續々 さすらいエマノン"]
    keywords = ["呪術廻戦"]
    
    for keyword in keywords:
        success = validator.validate_search(keyword)
        print("\n" + "="*60)
        if success:
            print(f"[OK] キーワード '{keyword}' での検索は成功")
        else:
            print(f"[NG] キーワード '{keyword}' での検索に問題があります")
        print("="*60 + "\n")
        
        # 複数キーワードの場合は遅延
        if keyword != keywords[-1]:
            print("[WAIT] 次のキーワード検索まで待機中... (5秒)")
            time.sleep(5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INFO] スクリプトが中断されました")
    except Exception as e:
        print(f"\n[ERROR] エラーが発生しました: {str(e)}")
