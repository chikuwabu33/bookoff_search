"""
深掘りHTML構造分析スクリプト
productItem の内部構造を詳細に調査
"""

import requests
from bs4 import BeautifulSoup
import json


def analyze_product_item():
    """productItem内の詳細構造を分析"""
    
    base_url = "https://shopping.bookoff.co.jp"
    search_url = f"{base_url}/search?keyword=續々 さすらいエマノン"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    print("[INFO] BOOKOFFサイトからHTMLを取得中...")
    response = requests.get(search_url, headers=headers, timeout=10)
    response.raise_for_status()
    print(f"[OK] 取得成功: {len(response.content)} bytes\n")
    
    soup = BeautifulSoup(response.content, "lxml")
    
    # productItem クラスを持つ div を取得
    product_items = soup.find_all("div", class_="productItem")
    print(f"[FOUND] productItem 要素: {len(product_items)} 個\n")
    
    if product_items:
        # 最初の1つのproductItemを詳しく調査
        first_item = product_items[0]
        
        print("="*60)
        print("最初のproductItem要素の内部構造:")
        print("="*60)
        
        # 最初の商品要素のHTML全体を表示
        print("\n[HTML全体]:")
        print(first_item.prettify()[:2000])  # 最初の2000文字
        
        # タイトル候補
        print("\n[タイトル候補]:")
        for tag in ["h1", "h2", "h3", "h4", "h5", "h6", "a", "span"]:
            elem = first_item.find(tag)
            if elem:
                text = elem.get_text(strip=True)
                if text:
                    print(f"  {tag}: {text[:80]}")
        
        # 価格候補
        print("\n[価格候補]:")
        for elem in first_item.find_all(["span", "div", "p"]):
            text = elem.get_text(strip=True)
            if any(char.isdigit() for char in text) and ("円" in text or "¥" in text or len(text) < 20):
                class_attr = " ".join(elem.get("class", []))
                print(f"  {elem.name} (class='{class_attr}'): {text[:80]}")
        
        # リンク候補
        print("\n[リンク候補]:")
        for link in first_item.find_all("a", href=True):
            href = link.get("href", "")
            text = link.get_text(strip=True)[:40]
            class_attr = " ".join(link.get("class", []))
            print(f"  href: {href[:80]}")
            print(f"  class: {class_attr}")
            print(f"  text: {text}")
            print()
        
        # 画像候補
        print("\n[画像候補]:")
        for img in first_item.find_all("img"):
            src = img.get("src", "")
            alt = img.get("alt", "")
            class_attr = " ".join(img.get("class", []))
            print(f"  src: {src[:80]}")
            print(f"  alt: {alt}")
            print(f"  class: {class_attr}")
            print()
        
        # productItem内のすべての子要素クラス
        print("\n[productItem内の直下の子要素]:")
        for child in first_item.children:
            if hasattr(child, 'name') and child.name:
                classes = " ".join(child.get("class", []))
                print(f"  {child.name}: class='{classes}'")


def analyze_all_items():
    """全商品アイテムの構造を一覧表示"""
    
    base_url = "https://shopping.bookoff.co.jp"
    search_url = f"{base_url}/search?keyword=續々 さすらいエマノン"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    response = requests.get(search_url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.content, "lxml")
    
    product_items = soup.find_all("div", class_="productItem")
    
    print("\n" + "="*60)
    print("全productItem要素の構造分析")
    print("="*60 + "\n")
    
    for idx, item in enumerate(product_items[:3], 1):  # 最初の3つを表示
        print(f"\n【商品 {idx}】")
        print("-"*40)
        
        # 各要素の抽出を試みる
        title = None
        price = None
        url = None
        image = None
        
        # タイトル: productItem__link か h3 を探す
        title_link = item.find("a", class_="productItem__link")
        if not title_link:
            title_link = item.find("a", class_="productItem__image")
        if title_link:
            title = title_link.get("title") or title_link.get_text(strip=True)
            url = title_link.get("href", "")
        
        if not title:
            title_elem = item.find("h3") or item.find("h4")
            if title_elem:
                title = title_elem.get_text(strip=True)
        
        # 価格: productItem__priceValue をさがす
        price_span = item.find("span", class_="productItem__moneyUnit")
        if price_span:
            # 親要素から価格を取得
            price_parent = price_span.parent
            if price_parent:
                price = price_parent.get_text(strip=True)
        
        if not price:
            for span in item.find_all("span"):
                text = span.get_text(strip=True)
                if any(char.isdigit() for char in text):
                    price = text
                    break
        
        # 画像
        img = item.find("img")
        if img:
            image = img.get("src", "")
        
        # URL用に絶対URLに変換
        if url and not url.startswith("http"):
            url = base_url + url
        
        print(f"タイトル: {title}")
        print(f"価格: {price}")
        print(f"URL: {url}")
        print(f"画像: {image[:60] if image else 'なし'}...")


if __name__ == "__main__":
    try:
        analyze_product_item()
        analyze_all_items()
    except Exception as e:
        print(f"[ERROR] エラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()
