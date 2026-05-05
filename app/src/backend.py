"""
FastAPI バックエンドアプリケーション
BOOKOFF検索機能をサポート
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import Depends
import requests
from contextlib import asynccontextmanager
from bs4 import BeautifulSoup
import logging
import time
import random
import urllib.parse # Keep this for search query encoding
import unicodedata
import re
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from database import get_db, init_db_tables
from models import ApiLog, MatchLog

JST = timezone(timedelta(hours=9))

def get_jst_now():
    """JST (日本標準時) の現在時刻を naive datetime として取得"""
    return datetime.now(JST).replace(tzinfo=None)

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# Playwrightが実行できない場合のフォールバック制御
_playwright_failed = False

from dotenv import load_dotenv # 追加
from typing import List, Optional # Add these imports
# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# .envファイルから環境変数を読み込む
load_dotenv() # 追加

# バックエンドURL設定 (追加)
BACKEND_URL = os.getenv("BACKEND_URL", None)
if BACKEND_URL:
    logger.info(f"Backend URL configured: {BACKEND_URL}")

# グローバルプロキシ変数
BOOKOFF_PROXY_URL = os.getenv("BOOKOFF_PROXY_URL", None)

# グローバルセッション（複数のリクエスト間でクッキーを保持するために必要）
_global_bookoff_session = None

def get_global_bookoff_session():
    """
    BOOKOFFアクセス用のグローバルなセッションオブジェクトを取得します。
    初回呼び出し時にセッションの初期化、ヘッダー設定、およびWAF回避のためのウォームアップを行います。

    Returns:
        requests.Session: 初期化済みのセッションオブジェクト
    """
    global _global_bookoff_session
    if _global_bookoff_session is None:
        _global_bookoff_session = requests.Session()
        _global_bookoff_session.trust_env = False
        headers = get_random_headers()
        _global_bookoff_session.headers.update(headers)
        _global_bookoff_session.headers['Accept-Encoding'] = 'gzip, deflate, br'
        _global_bookoff_session.headers['Connection'] = 'keep-alive'
        _global_bookoff_session.headers['DNT'] = '1'
        _global_bookoff_session.headers['TE'] = 'trailers'

        if BOOKOFF_PROXY_URL:
            _global_bookoff_session.proxies = {"http": BOOKOFF_PROXY_URL, "https": BOOKOFF_PROXY_URL}
        else:
            _global_bookoff_session.proxies = {}

        # 初回セッション化時に根ページをフェッチしてクッキーを取得、その後簡単な検索もする
#        try:
#            time.sleep(random.uniform(0.5, 1.5))
#            resp_root = _global_bookoff_session.get("https://shopping.bookoff.co.jp/", timeout=20)
#            logger.debug(f"Global Bookoff session initialized: root status={resp_root.status_code}")
#            if resp_root.status_code == 503:
#                logger.warning("Bookoff root returned 503 during session init; retrying with refreshed headers.")
#                _global_bookoff_session.cookies.clear()
#                _global_bookoff_session.headers.update(get_random_headers())
#                time.sleep(random.uniform(1.0, 2.0))
#                resp_root = _global_bookoff_session.get("https://shopping.bookoff.co.jp/", timeout=20)
#                logger.debug(f"Global Bookoff session reinitialized: root status={resp_root.status_code}")
#
#            # WAFの検知を回避するために簡単な検索もしておく
#            time.sleep(random.uniform(2.0, 4.0))
#            warmup_url = "https://shopping.bookoff.co.jp/search/keyword/python%20"
#            resp_search = _global_bookoff_session.get(
#                warmup_url,
#                headers={"Referer": "https://shopping.bookoff.co.jp/"},
#                timeout=20
#            )
#            logger.debug(f"Global Bookoff session warmed up: search status={resp_search.status_code}")
#            if resp_search.status_code == 503:
#                logger.warning("Bookoff warmup search returned 503; retrying once.")
#                time.sleep(random.uniform(2.0, 3.0))
#                resp_search = _global_bookoff_session.get(
#                    warmup_url,
#                    headers={"Referer": "https://shopping.bookoff.co.jp/"},
#                    timeout=20
#                )
#                logger.debug(f"Global Bookoff session warmed up after retry: search status={resp_search.status_code}")
#        except Exception as e:
#            logger.warning(f"Failed to initialize/warm up global Bookoff session: {e}")
    return _global_bookoff_session

@asynccontextmanager
async def lifespan(app: FastAPI):
    # データベースディレクトリの作成と権限確認
    db_url = os.getenv("DATABASE_URL", "sqlite:///./data/bookoff_search.db")
    if "sqlite" in db_url:
        data_dir = os.getenv("DATA_DIR", "/app/data")
        os.makedirs(data_dir, exist_ok=True)
        # 書き込み権限テスト
        test_file = os.path.join(data_dir, ".write_test")
        try:
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            logger.error(f"CRITICAL: データベースディレクトリへの書き込み権限がありません: {data_dir} - {e}")

    init_db_tables()
    setup_automatic_proxy()
    yield
    # Clean up resources if necessary

app = FastAPI(title="BOOKOFF Search API", version="1.0.0", lifespan=lifespan)

def setup_automatic_proxy():
    """
    CyberSyndrome (https://www.cybersyndrome.net/) からプロキシリストを取得し、
    BOOKOFFへのアクセスが可能なプロキシを自動探索してグローバル変数に設定します。
    """
    global BOOKOFF_PROXY_URL
    
    # 環境変数ですでに指定されている場合はそれを優先する（オプション）
    if BOOKOFF_PROXY_URL:
        logger.info(f"環境変数からプロキシを使用します: {BOOKOFF_PROXY_URL}")
        return

    logger.info("自動プロキシ探索を開始します: https://www.cybersyndrome.net/plr6.html")
    source_url = "https://www.cybersyndrome.net/plr6.html"
    test_target = "https://shopping.bookoff.co.jp/"
    
    try:
        resp = requests.get(source_url, headers=get_random_headers(), timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        
        # プロキシ候補の抽出
        candidates = []
        # CyberSyndromeの構造に合わせてテーブル行を解析
        rows = soup.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            # 通常、2列目にIP:Port、3列目に匿名性ランクがある
            if len(cols) >= 3:
                address = cols[1].get_text(strip=True)
                anonymity = cols[2].get_text(strip=True)
                
                # IP:Portの形式チェックと匿名性Dの除外
                if ":" in address and "D" not in anonymity:
                    candidates.append(address)

        logger.info(f"{len(candidates)} 件のプロキシ候補が見つかりました。接続テストを開始します...")

        for addr in candidates[:20]:  # 上位20件を試行
            proxy_url = f"http://{addr}"
            try:
                # 実際にBOOKOFFにアクセスできるかテスト（タイムアウトは短めに設定）
                test_resp = requests.Session()
                test_resp.trust_env = False
                test_resp.headers.update(get_random_headers())
                test_resp.headers['Accept-Encoding'] = 'gzip, deflate, br'
                test_resp = test_resp.get(test_target, 
                                         proxies={"http": proxy_url, "https": proxy_url}, 
                                         timeout=7)
                if test_resp.status_code == 200:
                    logger.info(f"使用可能なプロキシを発見しました: {proxy_url}")
                    BOOKOFF_PROXY_URL = proxy_url
                    return
            except Exception:
                continue
                
        logger.warning("使用可能なプロキシが見つかりませんでした。プロキシなしで続行します。")
    except Exception as e:
        logger.error(f"プロキシリストの取得中にエラーが発生しました: {e}")

# Pydantic models for log responses (for API endpoints)
class ApiLogResponse(BaseModel):
    id: int
    timestamp: datetime
    endpoint: str
    status: int

class MatchLogResponse(BaseModel):
    id: int
    timestamp: datetime
    keyword: str
    title: str

def log_api_call(db: Session, endpoint: str, status: int):
    """API実行状況をDB1に記録し、3日以上前のログを削除"""
    try:
        # 新しいログを記録
        api_log = ApiLog(endpoint=endpoint, status=status)
        db.add(api_log)
        
        # 3日分を過ぎたレコードを削除
        three_days_ago = get_jst_now() - timedelta(days=3)
        db.query(ApiLog).filter(ApiLog.timestamp < three_days_ago).delete()
        
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"DB1 Logging Error: {e}")

def log_match_found(db: Session, keyword: str, title: str):
    """
    検索条件に合致した商品をデータベースに記録します。
    過剰な記録を防ぐため、同じタイトルの商品は1時間以内に一度だけ記録されるように制限されています。

    Args:
        db (Session): SQLAlchemy データベースセッション
        keyword (str): 検索に使用されたキーワード
        title (str): 合致した商品のタイトル
    """
    try:
        # 1時間以内に同じタイトルが記録されているかチェック
        one_hour_ago = get_jst_now() - timedelta(hours=1)
        existing_log = db.query(MatchLog).filter(
            MatchLog.title == title,
            MatchLog.timestamp > one_hour_ago
        ).first()

        if existing_log:
            logger.info(f"DB記録スキップ (1時間以内の重複): {title}")
            return
        
        # 新しいログを記録
        match_log = MatchLog(keyword=keyword, title=title)
        db.add(match_log)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"DB2 Logging Error: {e}")

def normalize_text(text: str) -> str:
    """
    文字列の比較精度を高めるために、全角半角の統一、記号や空白の除去、および小文字化を行います。

    Args:
        text (str): 正規化対象の文字列
    Returns:
        str: 正規化された文字列
    """
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
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0"
]

def get_random_headers() -> dict:
    """
    ボット検知を回避するため、ランダムな User-Agent と標準的なブラウザヘッダーを生成します。

    Returns:
        dict: ブラウザを模倣したHTTPヘッダー辞書
    """
    user_agent = random.choice(USER_AGENTS)
    platform = '"Windows"' if 'Windows' in user_agent else '"macOS"'

    return {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "max-age=0",
        "Pragma": "no-cache",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Sec-GPC": "1",
        "sec-ch-ua": '"Google Chrome";v="124", "Chromium";v="124", "Not:A-Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": platform,
        "Referer": "https://shopping.bookoff.co.jp/"
    }

def initialize_bookoff_session(session: requests.Session, headers: dict):
    """
    引数で受け取った requests セッションに対し、ヘッダー、プロキシ設定を適用し、
    BOOKOFFのトップページにアクセスして必要なクッキーを初期化します。

    Args:
        session (requests.Session): 設定対象のセッション
        headers (dict): 適用するヘッダー辞書
    """
    session.trust_env = False
    session.headers.update(headers)
    session.headers['Accept-Encoding'] = 'gzip, deflate, br'

    if BOOKOFF_PROXY_URL:
        session.proxies = {"http": BOOKOFF_PROXY_URL, "https": BOOKOFF_PROXY_URL}
    else:
        session.proxies = {}

    # 少しだけランダムな待機を挿入して、自然なブラウジング挙動を模倣
    time.sleep(random.uniform(0.5, 1.5))

    try:
        resp = session.get("https://shopping.bookoff.co.jp/", timeout=20)
        logger.debug(f"Bookoff session init home status={resp.status_code}, cookies={session.cookies.get_dict()}")
    except requests.exceptions.RequestException as e:
        logger.warning(f"Bookoff セッション初期化時に警告が発生しました: {e}")


@dataclass
class BrowserResponse:
    """
    Playwright で取得したレスポンスを requests 互換のインターフェースで保持するためのデータクラス。
    """
    status_code: int
    content: bytes
    url: str

    def raise_for_status(self):
        """ステータスコードがエラー（400以上）の場合に例外をスローします。"""
        if 400 <= self.status_code:
            raise requests.exceptions.HTTPError(f"{self.status_code} Server Error: {self.url}")


async def fetch_with_playwright(url: str, headers: dict = None, timeout: int = 30) -> BrowserResponse:
    """
    Playwright (Chromium) を使用して指定されたURLのページをレンダリングし、HTMLコンテンツを取得します。
    JavaScriptの実行が必要なページや、単純なHTTPリクエストがブロックされる場合に有効です。

    Args:
        url (str): 取得対象のURL
        headers (dict, optional): カスタムヘッダー
        timeout (int): タイムアウト秒数
    Returns:
        BrowserResponse: ステータスコードとコンテンツを含むオブジェクト
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("Playwright is not installed")

    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"])
            context = await browser.new_context(
                user_agent=headers.get("User-Agent") if headers and "User-Agent" in headers else random.choice(USER_AGENTS),
                locale="ja-JP",
                viewport={"width": 1920, "height": 1080},
                java_script_enabled=True,
                accept_downloads=False,
                bypass_csp=True,
                color_scheme="light"
            )
            await context.set_extra_http_headers({
                "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
                "DNT": "1",
                "Sec-GPC": "1",
                "Upgrade-Insecure-Requests": "1"
            })
            page = await context.new_page()
            referer = headers.get("Referer") if headers and "Referer" in headers else "https://shopping.bookoff.co.jp/"
            # networkidle は遅いため、load (または commit) に変更
            response = await page.goto(url, wait_until="load", timeout=timeout * 1000, referer=referer)
            if response is None:
                raise RuntimeError("Playwright failed to load the page")
            html = await page.content()
            status = response.status if response.status is not None else 200
            return BrowserResponse(status_code=status, content=html.encode("utf-8"), url=url)
    finally:
        if browser:
            await browser.close()


async def fetch_with_retry(url: str, headers: dict = None, retries: int = 5, backoff_factor: float = 3.0):
    """
    BOOKOFFサイトへのリクエストをリトライ機能付きで実行します。
    Playwrightが利用可能な場合はブラウザレンダリングを優先し、失敗した場合は requests セッションへフォールバックします。
    指数バックオフを用いた待機処理を含みます。

    Args:
        url (str): リクエスト先URL
        headers (dict, optional): HTTPヘッダー
        retries (int): 最大リトライ回数
        backoff_factor (float): バックオフ計算の係数
    Returns:
        Union[BrowserResponse, requests.Response]: レスポンスオブジェクト
    """
    global _playwright_failed
    import asyncio
    status_forcelist = {429, 500, 502, 503, 504}

    for attempt in range(1, retries + 1):
        try:
            # ランダムな待機（ボット検知回避と自然なアクセス間隔）
            wait_time = random.uniform(1.0, 2.0) if attempt == 1 else random.uniform(4.0, 7.0)
            await asyncio.sleep(wait_time)

            # 1. まずは高速な requests で試行
            session = get_global_bookoff_session()
            request_headers = dict(session.headers)
            if headers:
                request_headers.update(headers)
            request_headers['Referer'] = "https://shopping.bookoff.co.jp/"
            request_headers['Accept-Encoding'] = "gzip, deflate, br"
            request_headers['Connection'] = "keep-alive"
            request_headers['Upgrade-Insecure-Requests'] = "1"
            request_headers['Sec-Fetch-Dest'] = "document"
            request_headers['Sec-Fetch-Mode'] = "navigate"
            request_headers['Sec-Fetch-Site'] = "same-origin"
            request_headers['Sec-Fetch-User'] = "?1"
            request_headers['sec-ch-ua-mobile'] = "?0"
            request_headers['sec-ch-ua-platform'] = '"Windows"'
            request_headers['Sec-GPC'] = "1"

            try:
                response = session.get(url, headers=request_headers, timeout=20)
                
                # もし 503 や 403 でブロックされた場合、Playwright に切り替えてリトライ
                if response.status_code in status_forcelist or response.status_code == 403:
                    if PLAYWRIGHT_AVAILABLE and not _playwright_failed:
                        logger.info(f"Requests blocked (status={response.status_code}). Switching to Playwright...")
                        response = await fetch_with_playwright(url, headers=headers, timeout=20)
            except Exception as e:
                if PLAYWRIGHT_AVAILABLE and not _playwright_failed:
                    logger.warning(f"Requests failed: {e}. Retrying with Playwright...")
                    response = await fetch_with_playwright(url, headers=headers, timeout=20)
                else:
                    raise

            status = response.status_code
            logger.info(f"fetch_with_retry: attempt={attempt}, status={status}, url={url}")

            if status in status_forcelist:
                if attempt == retries:
                    response.raise_for_status()
                sleep_seconds = backoff_factor * attempt + random.uniform(1, 3)
                logger.warning(f"リトライ対象エラー: status={status}。{sleep_seconds:.2f}s後に再試行します ({attempt}/{retries})")
                await asyncio.sleep(sleep_seconds)
                continue

            response.raise_for_status()
            return response

        except Exception as e:
            if isinstance(e, requests.exceptions.RequestException):
                if attempt == retries:
                    logger.error(f"fetch_with_retry: 最終試行失敗: {e}")
                    raise
                sleep_seconds = backoff_factor * attempt + random.uniform(1, 3)
                logger.warning(f"リクエストエラー: {e}。{sleep_seconds:.2f}s後に再試行します ({attempt}/{retries})")
                await asyncio.sleep(sleep_seconds)
                continue
            if attempt == retries:
                logger.error(f"fetch_with_retry: 最終試行失敗: {e}")
                raise
            sleep_seconds = backoff_factor * attempt + random.uniform(1, 3)
            logger.warning(f"一般エラー: {e}。{sleep_seconds:.2f}s後に再試行します ({attempt}/{retries})")
            await asyncio.sleep(sleep_seconds)
            continue

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


@app.api_route("/health", methods=["GET", "HEAD"])
def health_check():
    """ヘルスチェックエンドポイント"""
    return {"status": "healthy"}

@app.api_route("/", methods=["GET", "HEAD"])
def read_root():
    """ルートパスへのアクセスに対する応答（ヘルスチェック用）"""
    return {"message": "BOOKOFF Search API is running"}


# --- ログ取得・削除用APIエンドポイント ---
@app.get("/api/logs/api_calls", response_model=List[ApiLogResponse])
async def get_api_logs_backend(db: Session = Depends(get_db), limit: int = 50):
    """API実行ログを取得"""
    # timestampはDBに保存されたJST時刻なので、そのまま返す
    logs = db.query(ApiLog).order_by(ApiLog.timestamp.desc()).limit(limit).all()
    return logs

@app.get("/api/logs/match_history", response_model=List[MatchLogResponse])
async def get_match_history_backend(db: Session = Depends(get_db), limit: int = 50):
    """発見履歴ログを取得"""
    # timestampはDBに保存されたJST時刻なので、そのまま返す
    logs = db.query(MatchLog).order_by(MatchLog.timestamp.desc()).limit(limit).all()
    return logs

@app.delete("/api/logs/api_calls/clear")
async def clear_api_logs_backend(db: Session = Depends(get_db)):
    """API実行ログをすべて削除"""
    try:
        db.query(ApiLog).delete()
        db.commit()
        logger.info("API logs cleared successfully.")
        return {"message": "API logs cleared successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to clear API logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear API logs: {e}")

@app.delete("/api/logs/match_history/clear")
async def clear_match_history_backend(db: Session = Depends(get_db)):
    """発見履歴ログをすべて削除"""
    try:
        db.query(MatchLog).delete()
        db.commit()
        logger.info("Match history cleared successfully.")
        return {"message": "Match history cleared successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to clear match history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear match history: {e}")

# --- ログ取得・削除用APIエンドポイントここまで ---


@app.post("/api/search", response_model=SearchResponse)
async def search_bookoff(request: SearchRequest, db: Session = Depends(get_db)):
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
        # 末尾にスペースを追加することで検索ヒット率を向上させる
        search_query = re.sub(r'\s+', ' ', query.replace('(', ' ').replace(')', ' ').replace('（', ' ').replace('）', ' ')).strip() + " "
        encoded_query = urllib.parse.quote(search_query)
        search_url = f"https://shopping.bookoff.co.jp/search/keyword/{encoded_query}"
        
        # ヘッダー設定（ランダムなUser-Agentを使用してブロック回避）
        headers = get_random_headers()

        # BOOKOFFアクセス（エラー状態時のみ5回リトライ）
        response = await fetch_with_retry(search_url, headers=headers, retries=5, backoff_factor=3.0)

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
                if not title:
                    title = title_elem.get('title', '')

                # 在庫判定: 「カート」の文字が存在し、かつ「在庫なし」「品切れ」が含まれないことを確認
                item_text = item.get_text()
                has_cart_button = "カート" in item_text and "在庫なし" not in item_text and "品切れ" not in item_text
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
        
        log_api_call(db, "/api/search", 200)
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
        # HTTPExceptionの場合、status_codeはe.status_codeで取得できる
        log_api_call(db, "/api/search", getattr(e, 'status_code', 500))
        raise HTTPException(status_code=500, detail=f"検索処理でエラーが発生しました: {str(e)}")


@app.post("/api/stock", response_model=StockCheckResponse)
async def check_stock(request: SearchRequest, db: Session = Depends(get_db)):
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
        search_query = re.sub(r'\s+', ' ', keyword.replace('(', ' ').replace(')', ' ').replace('（', ' ').replace('）', ' ')).strip() + " "
        encoded_keyword = urllib.parse.quote(search_query)
        search_url = f"https://shopping.bookoff.co.jp/search/keyword/{encoded_keyword}"
        
        # ヘッダー設定（ランダムなUser-Agentを使用）
        headers = get_random_headers()
        
        # BOOKOFFアクセス（エラー状態時のみ5回リトライ）
        response = await fetch_with_retry(search_url, headers=headers, retries=5, backoff_factor=3.0)

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
                if not title:
                    title = title_elem.get('title', '')

                # 在庫判定
                item_text = item.get_text()
                has_cart_button = "カート" in item_text and "在庫なし" not in item_text and "品切れ" not in item_text
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
                log_match_found(db, keyword, r.title)
            log_api_call(db, "/api/stock", 200)
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
                log_match_found(db, keyword, r.title)
            log_api_call(db, "/api/stock", 200)
            return StockCheckResponse(
                keyword=keyword,
                in_stock=True,
                matching_count=len(partial_matching),
                match_type="部分一致",
                products=partial_matching[:10]
            )
        else:
            logger.info(f"在庫確認完了: {keyword} - 在庫なし")
            log_api_call(db, "/api/stock", 200)
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
    # FastAPIのHTTPExceptionはstatus_code属性を持つ
    except Exception as e:
        logger.error(f"エラー: {e}")
        log_api_call(db, "/api/stock", getattr(e, 'status_code', 500))
        raise HTTPException(status_code=500, detail=f"在庫確認処理でエラーが発生しました: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000)) # os.environ.get から os.getenv に変更し、.envから読み込む
    uvicorn.run(app, host="0.0.0.0", port=port)
