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

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BOOKOFF Search API", version="1.0.0")

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
        search_url = f"https://shopping.bookoff.co.jp/search?keyword={query}"
        
        # ヘッダー設定（User-Agentを指定してブロック回避）
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        # BOOKOFFアクセス（エラー状態時のみ3回リトライ）
        response = fetch_with_retry(search_url, headers=headers, retries=3, backoff_factor=1.0)

        # HTMLをパース
        soup = BeautifulSoup(response.content, "html.parser")
        
        # 検索結果を抽出
        results = []
        
        # 商品エレメントを検索（実際のBOOKOFF構造に対応）
        items = soup.find_all("div", class_="productItem")
        
        for item in items[:20]:  # 最初の20件を取得
            try:
                # 商品タイトルを抽出
                title_elem = item.find("p", class_="productItem__title")
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                
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
        search_url = f"https://shopping.bookoff.co.jp/search?keyword={keyword}"
        
        # ヘッダー設定
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        # BOOKOFFアクセス（エラー状態時のみ3回リトライ）
        response = fetch_with_retry(search_url, headers=headers, retries=3, backoff_factor=1.0)

        # HTMLをパース
        soup = BeautifulSoup(response.content, "html.parser")
        
        # 検索結果を抽出
        results = []
        items = soup.find_all("div", class_="productItem")
        
        for item in items[:30]:  # 最初の30件を確認
            try:
                title_elem = item.find("p", class_="productItem__title")
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                
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
        
        # キーワードを単語で分割
        keywords_parts = keyword.split()
        
        # 完全一致：全てのキーワード部分を含む商品
        fully_matching = [
            r for r in results 
            if all(part in r.title for part in keywords_parts if part)
        ]
        
        # 部分一致：いずれかのキーワード部分を含む商品
        partial_matching = [
            r for r in results 
            if any(part in r.title for part in keywords_parts if part)
        ]
        
        # 結果を判定
        if fully_matching:
            logger.info(f"在庫確認完了: {keyword} - 完全一致 {len(fully_matching)} 件")
            return StockCheckResponse(
                keyword=keyword,
                in_stock=True,
                matching_count=len(fully_matching),
                match_type="完全一致",
                products=fully_matching[:10]  # 最大10件まで返す
            )
        elif partial_matching:
            logger.info(f"在庫確認完了: {keyword} - 部分一致 {len(partial_matching)} 件")
            return StockCheckResponse(
                keyword=keyword,
                in_stock=True,
                matching_count=len(partial_matching),
                match_type="部分一致",
                products=partial_matching[:10]
            )
        else:
            logger.info(f"在庫確認完了: {keyword} - 在庫なし")
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
        raise HTTPException(status_code=500, detail=f"在庫確認処理でエラーが発生しました: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
