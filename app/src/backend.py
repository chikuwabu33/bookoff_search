"""
FastAPI バックエンドアプリケーション
BOOKOFF検索機能をサポート
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
import logging
import time
import random
import urllib.parse
import unicodedata
import re
import sqlite3
import os
from datetime import datetime

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# データベース設定
DATA_DIR = os.getenv("DATA_DIR", "data")
ABS_DATA_DIR = os.path.abspath(DATA_DIR)
DB1_PATH = os.path.join(DATA_DIR, "api_logs.db")
DB2_PATH = os.path.join(DATA_DIR, "match_logs.db")

def init_dbs():
    """データベースとテーブルの初期化"""
    os.makedirs(DATA_DIR, exist_ok=True)
    # DB1: API実行状況 (3日間保持)
    with sqlite3.connect(DB1_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS api_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME DEFAULT (DATETIME('now', 'localtime')), endpoint TEXT, status INTEGER)")
    # DB2: 在庫発見記録 (永続保持)
    with sqlite3.connect(DB2_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS match_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME DEFAULT (DATETIME('now', 'localtime')), keyword TEXT, title TEXT)")
    logger.info(f"Databases initialized at: {os.path.abspath(DATA_DIR)}")

def log_api_call(endpoint: str, status: int):
    """API実行状況をDB1に記録し、3日以上前のログを削除"""
    try:
        with sqlite3.connect(DB1_PATH) as conn:
            conn.execute("INSERT INTO api_logs (endpoint, status) VALUES (?, ?)", (endpoint, status))
            # 3日分を過ぎたレコードを削除
            conn.execute("DELETE FROM api_logs WHERE timestamp < datetime('now', 'localtime', '-3 days')")
    except Exception as e:
        logger.error(f"DB1 Logging Error: {e}")

def log_match_found(keyword: str, title: str):
    """発見した書籍をDB2に記録"""
    try:
        with sqlite3.connect(DB2_PATH) as conn:
            conn.execute("INSERT INTO match_logs (keyword, title) VALUES (?, ?)", (keyword, title))
    except Exception as e:
        logger.error(f"DB2 Logging Error: {e}")

app = FastAPI(title="BOOKOFF Search API", version="1.0.0")

init_dbs()

def normalize_text(text: str) -> str:
    """比較のためにテキストを正規化（全角半角統一、記号・空白削除、小文字化）"""
    if not text:
        return ""
    # NFKC正規化で全角英数字・記号を半角に変換
    normalized = unicodedata.normalize('NFKC', text)
    # 括弧、記号、空白を完全に除去
    normalized = re.sub(r'[()（）\[\]【】\s\-:：,，.．/／]', '', normalized)
    return normalized.lower()

# User-Agentリスト（ブラウザ情報を偽装するためにランダムに使用）
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0"
]

def get_random_headers() -> dict:
    """
    ランダムなUser-Agentと一般的なブラウザヘッダーを生成して返す
    これにより、ボットとして検知されるリスクを低減する
    """
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        "Referer": "https://shopping.bookoff.co.jp/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1"
    }

def fetch_with_retry(url: str, headers: dict, retries: int = 3, backoff_factor: float = 1.0):
    """BOOKOFFリクエスト: エラー(429/5xx/接続拒否など)時のみリトライ"""
    status_forcelist = {429, 500, 502, 503, 504}

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            logger.info(f"fetch_with_retry: attempt={attempt}, status={response.status_code}, url={url}")

            if response.status_code in status_forcelist:
                if attempt == retries:
                    response.raise_for_status()
                sleep_seconds = backoff_factor * attempt
                logger.warning(f"リトライ対象エラー: status={response.status_code}。{sleep_seconds}s後に再試行します ({attempt}/{retries})")
                time.sleep(sleep_seconds)
                continue

            # 成功 200、404などはここでリトライ停止
            response.raise_for_status()
            return response

        except requests.exceptions.RequestException as e:
            if attempt == retries:
                logger.error(f"fetch_with_retry: 最終試行失敗: {e}")
                raise
            sleep_seconds = backoff_factor * attempt
            logger.warning(f"リクエストエラー: {e}。{sleep_seconds}s後に再試行します ({attempt}/{retries})")
            time.sleep(sleep_seconds)

    raise RuntimeError("fetch_with_retry: リトライ上限に到達しました")

# CORS設定（Streamlitからのリクエストを許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    """検索リクエストモデル"""
    query: str


class SearchResult(BaseModel):
    """検索結果モデル"""
    title: str
    price: str
    url: str
    image_url: str = ""


class SearchResponse(BaseModel):
    """検索レスポンスモデル"""
    query: str
    count: int
    results: list[SearchResult]


class StockCheckResponse(BaseModel):
    """在庫確認レスポンスモデル"""
    keyword: str
    in_stock: bool
    matching_count: int
    match_type: str = ""  # "完全一致", "部分一致", "在庫なし"
    products: list[SearchResult] = []


@app.get("/health")
def health_check():
    """ヘルスチェックエンドポイント"""
    return {"status": "healthy"}


@app.post("/api/search", response_model=SearchResponse)
async def search_bookoff(request: SearchRequest):
    """
    BOOKOFF で検索を実行
    
    Args:
        request: 検索クエリを含むリクエスト
    
    Returns:
        検索結果のリスト
    """
    query = request.query.strip()
    
    if not query:
        raise HTTPException(status_code=400, detail="検索クエリが入力されていません")
    
    try:
        logger.info(f"検索開始: {query}")
        
        # BOOKOFF検索URL
        # 検索精度向上のため、括弧をスペースに置き換えて検索（Bookoffの検索エンジン仕様への対応）
        search_query = query.replace('(', ' ').replace(')', ' ').replace('（', ' ').replace('）', ' ')
        encoded_query = urllib.parse.quote(search_query)
        search_url = f"https://shopping.bookoff.co.jp/search/keyword/{encoded_query}"
        
        # ヘッダー設定（ランダムなUser-Agentを使用してブロック回避）
        headers = get_random_headers()

        # BOOKOFFアクセス（エラー状態時のみ3回リトライ）
        response = fetch_with_retry(search_url, headers=headers, retries=3, backoff_factor=1.0)

        # HTMLをパース
        soup = BeautifulSoup(response.content, "html.parser")
        
        # 検索結果を抽出
        results = []
        
        # 商品エレメントを検索
        items = soup.find_all("div", class_="productItem")
        logger.info(f"HTMLから抽出されたアイテム数: {len(items)}")
        
        for item in items[:40]:  # 取得件数を少し増やす
            try:
                # 商品タイトルを抽出
                title_elem = item.find("p", class_="productItem__title")
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)

                # 在庫確認: アイテム全体のHTML内に「カート」が含まれているか
                # ボタン要素(aタグやbuttonタグ)に限定して「カート」を探すことで、説明文との混同を防ぐ
                buttons_text = "".join([btn.get_text() for btn in item.find_all(['a', 'button'])])
                has_cart_button = "カート" in buttons_text
                if not has_cart_button:
                    logger.info(f"在庫なしスキップ: {title}")
                    continue
                
                if not title:
                    continue
                
                # 価格を抽出
                price_elem = item.find("p", class_="productItem__price")
                price = price_elem.get_text(strip=True) if price_elem else "価格不明"
                
                # URLを抽出
                url_elem = item.find("a", class_="productItem__link") or item.find("a", class_="productItem__image")
                url = url_elem.get("href") if url_elem else ""
                
                # 相対URLの場合は絶対URLに変換
                if url and not url.startswith("http"):
                    url = "https://shopping.bookoff.co.jp" + url
                
                # 画像URLを抽出
                img_elem = item.find("img")
                image_url = img_elem.get("src", "") if img_elem else ""
                
                if title and url:
                    logger.info(f"在庫あり商品を発見: {title}")
                    results.append(
                        SearchResult(
                            title=title,
                            price=price,
                            url=url,
                            image_url=image_url
                        )
                    )
            except Exception as e:
                logger.warning(f"商品情報の抽出エラー: {e}")
                continue
        
        logger.info(f"検索完了: {len(results)} 件の結果を取得")
        
        log_api_call("/api/search", 200)
        return SearchResponse(
            query=query,
            count=len(results),
            results=results
        )
        
    except requests.exceptions.RequestException as e:
        logger.error(f"リクエストエラー: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"BOOKOFFサイトにアクセスできません: {str(e)}"
        )
    except Exception as e:
        logger.error(f"エラー: {e}")
        if hasattr(e, 'status_code'):
            log_api_call("/api/search", e.status_code)
        raise HTTPException(status_code=500, detail=f"検索処理でエラーが発生しました: {str(e)}")


@app.post("/api/stock", response_model=StockCheckResponse)
async def check_stock(request: SearchRequest):
    """
    BOOKOFF で商品の在庫を確認
    
    キーワードで検索し、完全一致または部分一致する商品が存在するかを確認します。
    
    Args:
        request: 検索キーワードを含むリクエスト
    
    Returns:
        在庫確認結果（in_stock: True/False）
    """
    keyword = request.query.strip()
    
    if not keyword:
        raise HTTPException(status_code=400, detail="検索クエリが入力されていません")
    
    try:
        logger.info(f"在庫確認開始: {keyword}")
        
        # BOOKOFF検索URL
        # 検索精度向上のため、括弧をスペースに置き換えて検索
        search_query = keyword.replace('(', ' ').replace(')', ' ').replace('（', ' ').replace('）', ' ')
        encoded_keyword = urllib.parse.quote(search_query)
        search_url = f"https://shopping.bookoff.co.jp/search/keyword/{encoded_keyword}"
        
        # ヘッダー設定（ランダムなUser-Agentを使用）
        headers = get_random_headers()
        
        # BOOKOFFアクセス（エラー状態時のみ3回リトライ）
        response = fetch_with_retry(search_url, headers=headers, retries=3, backoff_factor=1.0)

        # HTMLをパース
        soup = BeautifulSoup(response.content, "html.parser")
        
        # 検索結果を抽出
        results = []
        items = soup.find_all("div", class_="productItem")
        logger.info(f"在庫確認: アイテム数 {len(items)}")
        
        for item in items[:50]:  # 最初の50件を確認
            try:
                title_elem = item.find("p", class_="productItem__title")
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)

                # 在庫判定
                buttons_text = "".join([btn.get_text() for btn in item.find_all(['a', 'button'])])
                has_cart_button = "カート" in buttons_text
                if not has_cart_button:
                    continue
                
                if not title:
                    continue
                
                price_elem = item.find("p", class_="productItem__price")
                price = price_elem.get_text(strip=True) if price_elem else "価格不明"
                
                url_elem = item.find("a", class_="productItem__link") or item.find("a", class_="productItem__image")
                url = url_elem.get("href") if url_elem else ""
                
                if url and not url.startswith("http"):
                    url = "https://shopping.bookoff.co.jp" + url
                
                img_elem = item.find("img")
                image_url = img_elem.get("src", "") if img_elem else ""
                
                if title and url:
                    results.append(
                        SearchResult(
                            title=title,
                            price=price,
                            url=url,
                            image_url=image_url
                        )
                    )
            except Exception as e:
                logger.warning(f"商品情報の抽出エラー: {e}")
                continue
        
        # キーワードを「空白」や「括弧」などの記号で細かく分割して判定を柔軟にする
        # 例: "転生したらスライムだった件(31)" -> ["転生したらスライムだった件", "31"]
        keywords_parts = re.split(r'[()（）\s]', keyword)
        normalized_parts = [normalize_text(p) for p in keywords_parts if p]
        logger.info(f"判定用キーワードパーツ: {normalized_parts}")
        
        # 全てのキーワードパーツ（タイトルと数字の両方）が含まれているものを抽出
        fully_matching = [
            r for r in results 
            if all(part in normalize_text(r.title) for part in normalized_parts)
        ]
        
        # 部分一致：いずれかのキーワード部分を含む商品
        partial_matching = [
            r for r in results 
            if any(part in normalize_text(r.title) for part in normalized_parts)
        ]
        
        # 結果を判定
        if fully_matching:
            logger.info(f"在庫確認完了: {keyword} - 完全一致 {len(fully_matching)} 件")
            for r in fully_matching:
                log_match_found(keyword, r.title)
            log_api_call("/api/stock", 200)
            return StockCheckResponse(
                keyword=keyword,
                in_stock=True,
                matching_count=len(fully_matching),
                match_type="完全一致",
                products=fully_matching[:10]  # 最大10件まで返す
            )
        elif partial_matching:
            logger.info(f"在庫確認完了: {keyword} - 部分一致 {len(partial_matching)} 件")
            for r in partial_matching:
                log_match_found(keyword, r.title)
            log_api_call("/api/stock", 200)
            return StockCheckResponse(
                keyword=keyword,
                in_stock=True,
                matching_count=len(partial_matching),
                match_type="部分一致",
                products=partial_matching[:10]
            )
        else:
            logger.info(f"在庫確認完了: {keyword} - 在庫なし")
            log_api_call("/api/stock", 200)
            return StockCheckResponse(
                keyword=keyword,
                in_stock=False,
                matching_count=0,
                match_type="在庫なし",
                products=[]
            )
        
    except requests.exceptions.RequestException as e:
        logger.error(f"リクエストエラー: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"BOOKOFFサイトにアクセスできません: {str(e)}"
        )
    except Exception as e:
        logger.error(f"エラー: {e}")
        if hasattr(e, 'status_code'):
            log_api_call("/api/stock", e.status_code)
        raise HTTPException(status_code=500, detail=f"在庫確認処理でエラーが発生しました: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
