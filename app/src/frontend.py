"""
BOOKOFF 在庫確認フロントエンド (Streamlit)
複数キーワードの入力・管理・在庫確認機能を提供
"""

import streamlit as st
import requests
import json
import time
import random
import datetime
import os
import logging
import csv
import urllib.parse
from typing import List, Dict

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- デフォルト設定項目 ---
# 自動検索を実行する時間帯 (24時間表記)
# この時間帯以外では、自動検索が有効でもAPI呼び出しは行われません。
DEFAULT_SEARCH_START_HOUR = 8  # 検索を開始する時刻 (例: 8 = 午前8時)
DEFAULT_SEARCH_END_HOUR = 17 # 検索を終了する時刻 (例: 24 = 23:59まで実行)
# --- 設定項目ここまで ---

# ページ設定
st.set_page_config(
    page_title="BOOKOFF 在庫確認",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS
st.markdown("""
    <style>
    .keyword-tag {
        background-color: #e8f4f8;
        padding: 8px 12px;
        border-radius: 20px;
        margin: 5px;
        display: inline-block;
        font-size: 14px;
    }
    .success-box {
        background-color: #d4edda;
        padding: 15px;
        border-radius: 5px;
        border-left: 4px solid #28a745;
        margin: 10px 0;
    }
    .error-box {
        background-color: #f8d7da;
        padding: 15px;
        border-radius: 5px;
        border-left: 4px solid #dc3545;
        margin: 10px 0;
    }
    </style>
""", unsafe_allow_html=True)

# バックエンド API URL
BACKEND_URL = os.getenv("BACKEND_URL", "http://bookoff_search_backend:8000")
WEBHOOK_URL = "https://trigger.macrodroid.com/44e2df0f-7ca1-48e3-9d14-74434fa947e8/BOOKOFF"

# キーワード保存用ファイル
DATA_DIR = os.getenv("DATA_DIR", "/app/data")
KEYWORDS_FILE = os.path.join(DATA_DIR, "keywords.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json") # 設定ファイルはローカルに保持

os.makedirs(DATA_DIR, exist_ok=True)

def reset_global_api_session():
    """
    Streamlit のセッションステートに保持されている API セッションをクリアします。
    通信エラーが頻発する場合などにセッションを再初期化するために使用されます。
    """
    if "_global_api_session" in st.session_state:
        st.session_state._global_api_session = None


def get_global_api_session():
    """
    バックエンド API と通信するためのグローバルなセッションオブジェクトを取得します。
    初回呼び出し時にセッションを生成し、ヘルスチェックとテスト検索によるウォームアップを行います。

    Returns:
        requests.Session: 初期化済みのセッション
    """
    if "_global_api_session" not in st.session_state or st.session_state._global_api_session is None:
        session = requests.Session()
        session.trust_env = False
        # ブラウザ風のヘッダーを設定
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Connection': 'keep-alive'
        })

        # セッションウォームアップ：ヘルスチェック後、簡単な在庫確認を行う
#        try:
#            time.sleep(random.uniform(0.5, 1.0))
#            resp_health = session.get(f"{BACKEND_URL}/health", timeout=5)
#            logger.debug(f"Global API session initialized: health status={resp_health.status_code}")
#
#            # WAFの検知を回避するために簡単な在庫確認もしておく
#            time.sleep(random.uniform(1.0, 2.0))
#            resp_warmup = session.post(
#                f"{BACKEND_URL}/api/stock",
#                json={"query": "Python"},
#                timeout=60
#            )
#            logger.debug(f"Global API session warmed up: warmup status={resp_warmup.status_code}")
#        except Exception as e:
#            logger.warning(f"Failed to warm up global API session: {e}")

        st.session_state._global_api_session = session

    return st.session_state._global_api_session

def load_settings() -> Dict:
    default_settings = {
        "interval_seconds": 60, # デフォルト60秒
        "last_notification_sent_date": "",
        "search_start_hour": DEFAULT_SEARCH_START_HOUR,
        "search_end_hour": DEFAULT_SEARCH_END_HOUR,
        "auto_loop": False # 自動検索のON/OFF状態も保存対象に追加
    }
    abs_path = os.path.abspath(SETTINGS_FILE)
    logger.info(f"Attempting to load settings from: {abs_path}")
    if os.path.exists(abs_path):
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
                default_settings.update(saved)
                logger.info(f"Settings successfully loaded from {abs_path}")
                return default_settings
        except Exception as e:
            logger.error(f"Error loading settings from {abs_path}: {e}")
    return default_settings


def save_settings(settings: Dict):
    """
    現在の設定を settings.json ファイルに保存します。

    Args:
        settings (Dict): 保存する設定内容の辞書
    """
    abs_path = os.path.abspath(SETTINGS_FILE)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    try:
        with open(abs_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
            logger.info(f"Settings successfully saved to {abs_path}")
    except Exception as e:
        logger.error(f"Error saving settings to {abs_path}: {e}")


def is_within_search_window() -> bool:
    """
    現在時刻 (JST) が、設定された「開始時刻」と「終了時刻」の範囲内にあるかどうかを判定します。

    Returns:
        bool: 時間内であれば True
    """
    # JST (UTC+9) タイムゾーンを指定して現在時刻を取得
    jst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(jst)
    now_hour = now.hour # JSTの現在時刻
    # 設定値から開始・終了時刻を取得
    search_start_hour = int(st.session_state.settings.get("search_start_hour", DEFAULT_SEARCH_START_HOUR))
    search_end_hour = int(st.session_state.settings.get("search_end_hour", DEFAULT_SEARCH_END_HOUR))

    if search_start_hour == search_end_hour:
        return True  # 開始と終了が同じなら24時間稼働とみなす
    if search_start_hour < search_end_hour:
        # 通常の範囲判定 (例: 8時から17時)
        return search_start_hour <= now_hour < search_end_hour
    else:
        # 日を跨ぐ場合 (例: 22時から翌5時)
        return now_hour >= search_start_hour or now_hour < search_end_hour

def get_effective_interval_seconds() -> int:
    """
    設定された検索実行間隔（秒）を返します。

    Returns:
        int: 次回検索までの秒数
    """
    return int(st.session_state.settings.get("interval_seconds", 60))

def get_match_history(limit: int = 50) -> List[Dict]:
    """
    バックエンド API から商品の発見履歴ログを取得します。

    Args:
        limit (int): 取得する最大件数
    Returns:
        List[Dict]: 履歴情報のリスト
    """
    try:
        session = get_global_api_session()
        response = session.get(f"{BACKEND_URL}/api/logs/match_history", params={"limit": limit}, timeout=10)
        response.raise_for_status() # HTTPエラーが発生した場合に例外を発生させる
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching match history from backend: {e}")
        return []

def get_api_logs(limit: int = 50) -> List[Dict]:
    """
    バックエンド API からシステムの実行状況ログを取得します。

    Args:
        limit (int): 取得する最大件数
    Returns:
        List[Dict]: ログ情報のリスト
    """
    try:
        session = get_global_api_session()
        response = session.get(f"{BACKEND_URL}/api/logs/api_calls", params={"limit": limit}, timeout=10)
        response.raise_for_status() # HTTPエラーが発生した場合に例外を発生させる
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching API logs from backend: {e}")
        return []

def clear_api_logs():
    """
    バックエンドに対して、API実行状況ログの全消去を要求します。

    Returns:
        Tuple[bool, str]: 成功可否とメッセージ
    """
    try:
        session = get_global_api_session()
        response = session.delete(f"{BACKEND_URL}/api/logs/api_calls/clear", timeout=10)
        response.raise_for_status()
        return True, "API状況ログをすべて削除しました"
    except requests.exceptions.RequestException as e:
        logger.error(f"Error clearing API logs via backend: {e}")
        return False, f"削除中にエラーが発生しました: {e}"

def clear_match_history():
    """
    バックエンドに対して、商品発見履歴ログの全消去を要求します。

    Returns:
        Tuple[bool, str]: 成功可否とメッセージ
    """
    try:
        session = get_global_api_session()
        response = session.delete(f"{BACKEND_URL}/api/logs/match_history/clear", timeout=10)
        response.raise_for_status()
        return True, "発見履歴をすべて削除しました"
    except requests.exceptions.RequestException as e:
        logger.error(f"Error clearing match history via backend: {e}")
        return False, f"削除中にエラーが発生しました: {e}"


def get_db_csv_data(endpoint_path: str, file_prefix: str) -> bytes:
    """
    指定されたエンドポイントからログデータを取得し、Excelで開きやすいように
    BOM付きUTF-8エンコーディングのCSVバイナリデータを作成します。

    Args:
        endpoint_path (str): APIのエンドポイントパス
        file_prefix (str): ファイル名のプレフィックス（未使用だが識別用）
    Returns:
        bytes: 生成されたCSVデータのバイト列。データがない場合は None。
    """
    try:
        session = get_global_api_session()
        response = session.get(f"{BACKEND_URL}{endpoint_path}", timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data:
            return None

        import io
        output = io.StringIO()
        # ヘッダーを動的に取得
        fieldnames = data[0].keys() if data else []
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
        
        # Excel対応のためBOM付きUTF-8のバイト列に変換
        return output.getvalue().encode('utf-8-sig')
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data for CSV from backend ({endpoint_path}): {e}")
        return None
    except Exception as e:
        logger.error(f"Error generating CSV from backend data ({endpoint_path}): {e}")
        return None

def handle_clear_match_logs():
    """
    発見履歴ログをクリアするためのUIコールバック関数です。
    削除実行後、トースト通知を表示し、画面上の履歴表示をリセットします。
    """
    success, msg = clear_match_history()
    if success:
        st.toast(msg)
        if "show_history" in st.session_state:
            st.session_state.show_history = None
    else:
        st.error(msg)


def send_webhook_notification(product_name: str, product_url: str, force: bool = False) -> bool:
    """
    MacroDroid 等の外部通知ツールへ Webhook を送信します。

    Args:
        product_name (str): 通知する商品名
        product_url (str): 商品のURL
        force (bool): 重複チェックを無視して強制送信するかどうか
    Returns:
        bool: 送信に成功した場合は True
    """
    try:
        logger.info(f"MacroDroid通知送信開始: {product_name}")
        params = {
            "product": product_name,
            "url": product_url
        }
        # POSTからGETに変更 (MacroDroidのWebhookはGETリクエストでのパラメータ受け渡しが標準的です)
        response = requests.get(WEBHOOK_URL, params=params, timeout=10)
        if response.status_code == 200:
            logger.info("MacroDroid通知送信成功")
            return True
        else:
            logger.error(f"MacroDroid通知送信失敗: {response.status_code} {response.text}")
            return False
    except Exception as e:
        logger.error(f"MacroDroid通知送信エラー: {str(e)}")
        return False


def load_keywords() -> List[str]:
    abs_path = os.path.abspath(KEYWORDS_FILE)
    logger.info(f"Attempting to load keywords from: {abs_path}")
    if os.path.exists(abs_path):
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                keywords = json.load(f)
                logger.info(f"Keywords successfully loaded: {len(keywords)} items from {abs_path}")
                return keywords
        except Exception as e:
            logger.error(f"Error loading keywords from {abs_path}: {e}")
            return []
    # ファイルが存在しない場合は空のリストを返す
    logger.warning(f"Keywords file not found at: {abs_path}")
    return []


def save_keywords(keywords: List[str]):
    """
    指定されたキーワードリストを keywords.json に保存します。

    Args:
        keywords (List[str]): 保存するキーワードのリスト
    """
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
    abs_path = os.path.abspath(KEYWORDS_FILE)
    try:
        with open(abs_path, "w", encoding="utf-8") as f:
            json.dump(keywords, f, ensure_ascii=False, indent=2)
            logger.info(f"Keywords successfully saved to {abs_path}")
    except Exception as e:
        logger.error(f"Error saving keywords: {e}")


# セッションステートの初期化
def initialize_session_state():
    if "keywords" not in st.session_state:
        st.session_state.keywords = load_keywords()
    if "settings" not in st.session_state:
        st.session_state.settings = load_settings()
    if "keyword_input" not in st.session_state:
        st.session_state.keyword_input = ""
    if "stock_results" not in st.session_state:
        st.session_state.stock_results = None
    if "error_message" not in st.session_state:
        st.session_state.error_message = None
    if "auto_loop" not in st.session_state:
        st.session_state.auto_loop = st.session_state.settings.get("auto_loop", False)
    if "show_api_logs" not in st.session_state:
        st.session_state.show_api_logs = None
    if "confirm_delete_db1" not in st.session_state:
        st.session_state.confirm_delete_db1 = False
    if "confirm_delete_db2" not in st.session_state:
        st.session_state.confirm_delete_db2 = False
    if "last_run_time" not in st.session_state:
        st.session_state.last_run_time = None


def add_keyword_callback():
    """
    UIから新しいキーワードを追加するためのコールバック関数です。
    重複チェックを行い、新しければリストに保存して入力欄をクリアします。
    """
    if "keywords" not in st.session_state:
        st.session_state.keywords = load_keywords()

    keyword = st.session_state.keyword_input.strip()
    if keyword:
        if keyword not in st.session_state.keywords:
            st.session_state.keywords.append(keyword)
            save_keywords(st.session_state.keywords)
            # 入力欄をクリア（コールバック内での変更は安全です）
            st.session_state.keyword_input = ""
            st.session_state.error_message = None
            
            # 自動検索モードが有効な場合、即座に検索が走るようにタイマーをリセット
            if st.session_state.get("auto_loop"):
                st.session_state.last_run_time = None
        else:
            st.session_state.error_message = f"「{keyword}」は既に追加されています"
    else:
        st.session_state.error_message = "キーワードを入力してください"


def trigger_test_notification():
    """
    UIからテスト通知を手動で実行するためのコールバック関数です。
    """
    test_product = "テスト用商品（手動テスト）"
    test_url = "https://shopping.bookoff.co.jp"
    if send_webhook_notification(test_product, test_url, force=True):
        st.toast("✅ テスト通知を送信しました")
    else:
        st.toast("❌ テスト通知の送信に失敗しました")


def remove_keyword(keyword: str):
    """
    指定されたキーワードをリストおよび保存ファイルから削除します。

    Args:
        keyword (str): 削除対象のキーワード
    Returns:
        bool: 削除に成功した場合は True
    """
    if keyword in st.session_state.keywords:
        st.session_state.keywords.remove(keyword)
        save_keywords(st.session_state.keywords)
        # 検索結果からも削除して即座に画面表示を更新
        if st.session_state.stock_results and keyword in st.session_state.stock_results:
            del st.session_state.stock_results[keyword]
        st.session_state.error_message = None
        return True
    return False


def check_stock(keyword: str) -> Dict:
    """
    バックエンド API を呼び出して、特定のキーワードの在庫状況を確認します。
    接続エラーが発生した場合は一度だけセッションのリセットを試みます。

    Args:
        keyword (str): 検索キーワード
    Returns:
        Dict: APIからのレスポンスデータ。エラー時はエラー情報を含む辞書。
    """
    for attempt in range(1, 3):
        try:
            session = get_global_api_session()
            response = session.post(
                f"{BACKEND_URL}/api/stock",
                json={"query": keyword},
                timeout=120
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "error": True,
                    "message": f"エラー: {response.status_code}",
                    "detail": response.json().get("detail", "不明なエラー")
                }
        except requests.exceptions.RequestException as e:
            logger.warning(f"バックエンドAPI接続に失敗しました (attempt={attempt}): {e}")
            if attempt == 1:
                reset_global_api_session()
                continue
            return {
                "error": True,
                "message": "バックエンドサーバーに接続できません",
                "detail": f"{BACKEND_URL} が起動していることを確認してください: {str(e)}"
            }
        except Exception as e:
            logger.error(f"check_stock unexpected error: {e}")
            return {
                "error": True,
                "message": "エラーが発生しました",
                "detail": str(e)
            }


def check_all_keywords():
    """
    登録されているすべてのキーワードに対して、在庫確認を順次実行します。
    503エラー（アクセス制限）を回避するため、キーワードごとにランダムな待機時間を設けています。
    """
    if not st.session_state.keywords:
        st.session_state.error_message = "キーワードを追加してください"
        return
    
    results = {}
    for i, keyword in enumerate(st.session_state.keywords):
        # 2つ目以降のキーワード検索の前にランダムな待機時間を設けて503エラーを回避
        if i > 0:
            time.sleep(random.uniform(1.0, 3.0))
            
        results[keyword] = check_stock(keyword)
    
    st.session_state.stock_results = results
    st.session_state.error_message = None


def process_notifications(force: bool = False):
    """
    現在の在庫検索結果に基づき、在庫あり商品の通知（Webhook送信）を処理します。
    自動検索時は1日1回までの通知制限がありますが、force=True（手動実行時）は即時送信します。

    Args:
        force (bool): 日付チェックをスキップして強制的に通知を送信するか
    """
    logger.info("通知処理を開始します")
    if not st.session_state.stock_results:
        logger.info("在庫検索結果が空のため通知処理をスキップします")
        return

    # 通知判定 (在庫あり)
    in_stock_keywords = [
        k for k, r in st.session_state.stock_results.items()
        if not r.get("error") and r.get("in_stock")
    ]
    logger.info(f"在庫あり件数: {len(in_stock_keywords)}")
    
    if in_stock_keywords:
        today_str = datetime.date.today().isoformat()
        
        # 自動検索（force=False）の場合、今日すでに通知済みならスキップ
        # 手動検索（force=True）の場合はこのチェックを無視して送信する
        last_sent_date = st.session_state.settings.get("last_notification_sent_date", "")
        if not force and last_sent_date == today_str:
            logger.info(f"本日は既に通知済みのため、自動通知をスキップします (日付: {today_str})")
            return

        sent_count = 0
        for k in in_stock_keywords:
            res = st.session_state.stock_results[k]
            
            # 代表的な商品情報（1件目）を取得
            products = res.get("products", [])
            if products:
                top_product = products[0]
                product_name = f"{k} ({top_product['title'][:20]}...)"
                product_url = top_product['url']
                
                if send_webhook_notification(product_name, product_url, force=force):
                    sent_count += 1
                    time.sleep(1) # 連打防止
        
        if sent_count > 0:
            st.session_state.settings["last_notification_sent_date"] = today_str
            save_settings(st.session_state.settings)
            st.success(f"📱 {sent_count}件の通知をMacroDroidへ送信しました")


def execute_search_batch(force: bool = False):
    """
    全キーワードの在庫確認と、その後の通知処理を一括して実行します。

    Args:
        force (bool): 通知の強制送信フラグ
    """
    with st.spinner("在庫確認中..."):
        check_all_keywords()
        process_notifications(force=force)


def display_result_card(keyword: str, result: Dict):
    """
    特定のキーワードに対する在庫確認の結果を、Streamlit 上にカード形式で描画します。

    Args:
        keyword (str): 表示対象のキーワード
        result (Dict): APIからの検索結果データ
    """
    if result.get("error"):
        with st.container():
            st.markdown(f"""
                <div class="error-box">
                <strong>❌ {keyword}</strong><br>
                エラー: {result['message']}<br>
                詳細: {result['detail']}
                </div>
            """, unsafe_allow_html=True)
    else:
        in_stock = result.get("in_stock", False)
        match_type = result.get("match_type", "")
        count = result.get("matching_count", 0)
        products = result.get("products", [])
        
        if in_stock:
            st.markdown(f"""
                <div class="success-box">
                <strong>✅ {keyword}</strong><br>
                <strong>在庫状況:</strong> あり<br>
                <strong>マッチタイプ:</strong> {match_type}<br>
                <strong>件数:</strong> {count}件
                </div>
            """, unsafe_allow_html=True)
            
            # 商品一覧を表示
            if products:
                st.write("**該当商品（最初の10件）:**")
                for idx, product in enumerate(products, 1):
                    with st.expander(f"{idx}. {product['title'][:60]}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**価格:** {product['price']}")
                        with col2:
                            st.write(f"**URL:** [リンク]({product['url']})")
                        if product.get("image_url"):
                            st.write(f"**画像:** {product['image_url'][:80]}")
        else:
            # キーワード内の括弧をスペースに変換し、末尾にスペースを1つ追加（ユーザーが提示した成功URLの形式）
            search_query = keyword.replace('(', ' ').replace(')', ' ').replace('（', ' ').replace('）', ' ') + " "
            encoded_keyword = urllib.parse.quote(search_query)
            search_url = f"https://shopping.bookoff.co.jp/search/keyword/{encoded_keyword}"
            st.markdown(f"""
                <div class="error-box">
                <strong>❌ {keyword}</strong><br>
                <strong>在庫状況:</strong> なし<br>
                当サイトに在庫がない商品です。<br>
                URL: <a href="{search_url}" target="_blank">{search_url}</a>
                </div>
            """, unsafe_allow_html=True)


def main():
    initialize_session_state()
    
    # ヘッダー
    st.title("📚 BOOKOFF 在庫確認")
    st.markdown("---")
    
    # サイドバー - API接続状態確認
    with st.sidebar:
        st.header("⚙️ 設定")
        
        if st.button("API接続確認"):
            try:
                session = get_global_api_session()
                response = session.get(f"{BACKEND_URL}/health", timeout=5)
                if response.status_code == 200:
                    st.success("✅ バックエンド API: 接続成功")
                else:
                    st.error("❌ バックエンド API: 接続失敗")
            except Exception as e:
                st.error(f"❌ バックエンド API: 接続エラー\n{str(e)}")
        
        # テスト通知ボタン（コールバック方式で独立して動作）
        st.button("Webhook通知-テスト送信", on_click=trigger_test_notification)

        st.info(f"📍 API エンドポイント: {BACKEND_URL}")
        
        # キーワード管理セクション
        st.header("🔍 キーワード管理")
        
        # キーワード入力
        new_keyword = st.text_input(
            "キーワードを入力",
            placeholder="例：呪術廻戦",
            key="keyword_input"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            st.button("➕ 追加", width="stretch", on_click=add_keyword_callback)
        
        with col2:
            if st.button("🗑️ すべてクリア", width="stretch"):
                st.session_state.keywords = []
                save_keywords([])
                st.rerun()
        
        # 登録済みキーワード表示
        if st.session_state.keywords:
            st.subheader(f"登録済みキーワード ({len(st.session_state.keywords)} 個)")
            
            for keyword in st.session_state.keywords:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"📌 {keyword}")
                with col2:
                    if st.button("❌", key=f"remove_{keyword}", width="stretch"):
                        remove_keyword(keyword)
                        st.rerun()
        else:
            st.info("キーワードが登録されていません")

        st.markdown("---")
        st.header("⚙️ 自動検索設定")
        
        with st.expander("設定を開く", expanded=False):
            st.session_state.settings["interval_seconds"] = st.number_input(
                "検索間隔 (秒)", 
                min_value=5, 
                value=int(st.session_state.settings.get("interval_seconds", 60))
            )
            
            # 開始時刻と終了時刻の設定
            col1, col2 = st.columns(2)
            with col1:
                start_hour = st.number_input(
                    "開始時刻 (時)",
                    min_value=0,
                    max_value=23,
                    value=int(st.session_state.settings.get("search_start_hour", DEFAULT_SEARCH_START_HOUR))
                )
                st.session_state.settings["search_start_hour"] = start_hour
            
            with col2:
                end_hour = st.number_input(
                    "終了時刻 (時)",
                    min_value=0,
                    max_value=24,
                    value=int(st.session_state.settings.get("search_end_hour", DEFAULT_SEARCH_END_HOUR))
                )
                st.session_state.settings["search_end_hour"] = end_hour
            
            st.caption(f"検索実行時間帯: {int(st.session_state.settings['search_start_hour'])}:00 ～ {int(st.session_state.settings['search_end_hour'])}:00")
            
            if st.button("💾 設定を保存", width="stretch"):
                save_settings(st.session_state.settings)
                st.success("設定を保存しました")

        st.markdown("---")
        st.header("💾 ログ出力 (CSV)")

        # API状況ログ (DB1) のダウンロード
        api_csv = get_db_csv_data("/api/logs/api_calls", "api_logs")
        if api_csv:
            st.download_button(
                label="API状況ログを保存 (DB1)",
                data=api_csv,
                file_name=f"api_logs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                width="stretch"
            )
        else:
            st.button("API状況ログなし (DB1)", width="stretch", disabled=True)
            
        # 発見記録ログ (DB2) のダウンロード
        match_csv = get_db_csv_data("/api/logs/match_history", "match_logs")
        if match_csv:
            st.download_button(
                label="発見記録ログを保存 (DB2)",
                data=match_csv,
                file_name=f"match_logs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                width="stretch"
            )
        else:
            st.button("発見記録ログなし (DB2)", width="stretch", disabled=True)

        st.markdown("---")
        # API状況表示 (DB1)
        if st.button("📋 API状況を画面に表示 (DB1)", width="stretch"):
            st.session_state.show_api_logs = get_api_logs()
            st.session_state.show_history = None

        # 発見履歴表示 (DB2)
        if st.button("📋 発見履歴を画面に表示 (DB2)", width="stretch"):
            history = get_match_history()
            st.session_state.show_history = history if history else []
            st.session_state.show_api_logs = None

        st.markdown("---")
        # 削除ボタン (DB1)
        if st.button("🗑️ API状況ログを消去 (DB1)", width="stretch"):
            st.session_state.confirm_delete_db1 = True
        
        if st.session_state.confirm_delete_db1:
            st.warning("DB1のログをすべて消去しますか？")
            c1, c2 = st.columns(2)
            if c1.button("はい、削除 (DB1)", key="db1_yes", width="stretch"):
                success, msg = clear_api_logs()
                st.session_state.confirm_delete_db1 = False
                st.session_state.show_api_logs = None
                if success: st.toast(msg)
                else: st.error(msg)
                st.rerun()
            if c2.button("いいえ", key="db1_no", width="stretch"):
                st.session_state.confirm_delete_db1 = False
                st.rerun()

        # 削除ボタン (DB2)
        if st.button("🗑️ 発見履歴を消去 (DB2)", width="stretch"):
            st.session_state.confirm_delete_db2 = True

        if st.session_state.confirm_delete_db2:
            st.warning("DB2の履歴をすべて消去しますか？")
            c1, c2 = st.columns(2)
            if c1.button("はい、削除 (DB2)", key="db2_yes", width="stretch"):
                success, msg = clear_match_history()
                st.session_state.confirm_delete_db2 = False
                st.session_state.show_history = None
                if success: st.toast(msg)
                else: st.error(msg)
                st.rerun()
            if c2.button("いいえ", key="db2_no", width="stretch"):
                st.session_state.confirm_delete_db2 = False
                st.rerun()
    
    # メインコンテンツ
    st.header("📊 在庫確認")

    # 進行状況表示用のプレースホルダー (カウントダウンで使用)
    status_container = st.empty()
    
    # エラーメッセージ表示
    if st.session_state.error_message:
        st.error(st.session_state.error_message)
    
    # キーワード一覧表示
    if st.session_state.keywords:
        st.subheader("登録済みキーワード")
        cols = st.columns(min(4, len(st.session_state.keywords)))
        for idx, keyword in enumerate(st.session_state.keywords):
            with cols[idx % 4]:
                st.markdown(f"""
                    <div class="keyword-tag" style="text-align: center;">
                    {keyword}
                    </div>
                """, unsafe_allow_html=True)
        
        # 在庫確認ボタン
        st.markdown("---")
        
        col_act1, col_act2 = st.columns(2)
        with col_act1:
            if st.button("🔎 今すぐ検索", width="stretch", type="primary"):
                # 手動検索は強制実行 (force=True)
                execute_search_batch(force=True)
        
        with col_act2:
            if st.session_state.auto_loop:
                if st.button("⏹️ 自動検索を停止", width="stretch", type="secondary"):
                    st.session_state.settings["auto_loop"] = False
                    st.session_state.auto_loop = False
                    save_settings(st.session_state.settings)
                    st.rerun()
            else:
                def start_auto_loop():
                    st.session_state.settings["auto_loop"] = True
                    st.session_state.auto_loop = True
                    st.session_state.last_run_time = None
                    save_settings(st.session_state.settings)
                
                st.button("🔄 自動検索を開始", width="stretch", on_click=start_auto_loop)

        if st.session_state.auto_loop:
            current_interval_sec = get_effective_interval_seconds()
            st.success(f"🔄 自動検索モードが有効です (現在の実行間隔: {current_interval_sec}秒)")
            
            if not is_within_search_window():
                search_start_hour = int(st.session_state.settings.get("search_start_hour", DEFAULT_SEARCH_START_HOUR))
                search_end_hour = int(st.session_state.settings.get("search_end_hour", DEFAULT_SEARCH_END_HOUR))
                st.warning(f"現在時間外です。検索は {search_start_hour}:00～{search_end_hour}:00 の間に行われます。")
            st.info("※ バックエンドで自律的に実行されています。")

    else:
        st.info("📝 左のサイドバーからキーワードを追加してください")
    
    # API状況ログの表示
    if "show_api_logs" in st.session_state and st.session_state.show_api_logs is not None:
        st.markdown("---")
        st.subheader("📊 API状況ログ (DB1)")
        if st.session_state.show_api_logs:
            st.dataframe(
                st.session_state.show_api_logs,
                width="stretch",
                hide_index=True
            )
        else:
            st.write("データなし")
        if st.button("APIログ表示を閉じる"):
            st.session_state.show_api_logs = None
            st.rerun()

    # 発見履歴の表示 (ボタンが押された場合のみ)
    if "show_history" in st.session_state and st.session_state.show_history is not None:
        st.markdown("---")
        st.subheader("📜 最近の発見履歴 (DB2)")
        if st.session_state.show_history:
            st.dataframe(
                st.session_state.show_history,
                width="stretch",
                hide_index=True
            )
        else:
            st.write("データなし")
            
        if st.button("履歴表示を閉じる"):
            st.session_state.show_history = None
            st.rerun()

    # 結果表示
    if st.session_state.stock_results:
        st.markdown("---")
        st.subheader("📋 確認結果")
        
        # 統計情報
        col1, col2, col3 = st.columns(3)
        
        in_stock_count = sum(
            1 for r in st.session_state.stock_results.values()
            if not r.get("error") and r.get("in_stock")
        )
        out_of_stock_count = sum(
            1 for r in st.session_state.stock_results.values()
            if not r.get("error") and not r.get("in_stock")
        )
        error_count = sum(
            1 for r in st.session_state.stock_results.values()
            if r.get("error")
        )
        
        with col1:
            st.metric("✅ 在庫あり", in_stock_count)
        with col2:
            st.metric("❌ 在庫なし", out_of_stock_count)
        with col3:
            st.metric("⚠️ エラー", error_count)
        
        st.markdown("---")
        
        # 在庫ありの商品
        in_stock_keywords = [
            k for k, r in st.session_state.stock_results.items()
            if not r.get("error") and r.get("in_stock")
        ]
        if in_stock_keywords:
            st.markdown("### ✅ 在庫あり")
            for keyword in in_stock_keywords:
                st.subheader(keyword)
                display_result_card(keyword, st.session_state.stock_results[keyword])
                st.markdown("---")
        
        # 在庫なしの商品
        out_of_stock_keywords = [
            k for k, r in st.session_state.stock_results.items()
            if not r.get("error") and not r.get("in_stock")
        ]
        if out_of_stock_keywords:
            with st.expander("❌ 在庫なし"):
                for keyword in out_of_stock_keywords:
                    st.subheader(keyword)
                    display_result_card(keyword, st.session_state.stock_results[keyword])
        
        # エラーが発生した項目
        error_keywords = [
            k for k, r in st.session_state.stock_results.items()
            if r.get("error")
        ]
        if error_keywords:
            with st.expander("⚠️ エラー"):
                for keyword in error_keywords:
                    st.subheader(keyword)
                    display_result_card(keyword, st.session_state.stock_results[keyword])
if __name__ == "__main__":
    main()
