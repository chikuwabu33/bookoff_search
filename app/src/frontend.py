"""
BOOKOFF 在庫確認フロントエンド (Streamlit)
複数キーワードの入力・管理・在庫確認機能を提供
"""

import streamlit as st
import requests
import json
import time
import datetime
import os
import urllib.parse
import re
from typing import List, Dict

# --- 設定項目 ---
# 自動検索を実行する時間帯 (24時間表記)
# この時間帯以外では、自動検索が有効でもAPI呼び出しは行われません。
SEARCH_START_HOUR = 8  # 検索を開始する時刻 (例: 8 = 午前8時)
SEARCH_END_HOUR = 17 # 検索を終了する時刻 (例: 24 = 23:59まで実行)
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
BACKEND_URL = "http://backend:8000"
WEBHOOK_URL = "https://trigger.macrodroid.com/44e2df0f-7ca1-48e3-9d14-74434fa947e8/BOOKOFF"

# キーワード保存用ファイル
KEYWORDS_FILE = "keywords.json"
SETTINGS_FILE = "settings.json"


def load_settings() -> Dict:
    """設定を読み込む"""
    default_settings = {
        "interval_minutes": 60,
        "last_notification_sent_date": ""
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                default_settings.update(saved)
                return default_settings
        except Exception:
            pass
    return default_settings


def save_settings(settings: Dict):
    """設定を保存"""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving settings: {e}")


def is_within_search_window() -> bool:
    """現在の時刻が検索実行時間帯内か判定する"""
    # JST (UTC+9) タイムゾーンを指定して現在時刻を取得
    jst = datetime.timezone(datetime.timedelta(hours=9))
    now_hour = datetime.datetime.now(jst).hour
    # SEARCH_END_HOUR は含まない (例: 24なら23:59までOK)
    return SEARCH_START_HOUR <= now_hour < SEARCH_END_HOUR


def send_webhook_notification(product_name: str, product_url: str, force: bool = False) -> bool:
    """
    MacroDroidへ通知を送信
    """
    try:
        print(f"[DEBUG] MacroDroid通知送信開始: {product_name}")
        params = {
            "product": product_name,
            "url": product_url
        }
        # POSTからGETに変更 (MacroDroidのWebhookはGETリクエストでのパラメータ受け渡しが標準的です)
        response = requests.get(WEBHOOK_URL, params=params, timeout=10)
        if response.status_code == 200:
            print("[DEBUG] MacroDroid通知送信成功")
            return True
        else:
            print(f"[ERROR] MacroDroid通知送信失敗: {response.status_code} {response.text}")
            return False
    except Exception as e:
        print(f"[ERROR] MacroDroid通知送信エラー: {str(e)}")
        return False


def load_keywords() -> List[str]:
    """保存されたキーワードを読み込む"""
    if os.path.exists(KEYWORDS_FILE):
        try:
            with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_keywords(keywords: List[str]):
    """キーワードをファイルに保存"""
    try:
        with open(KEYWORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(keywords, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving keywords: {e}")


# セッションステートの初期化
def initialize_session_state():
    """セッションステートを初期化"""
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
        st.session_state.auto_loop = False
    if "last_run_time" not in st.session_state:
        st.session_state.last_run_time = None


def add_keyword_callback():
    """キーワードをリストに追加するコールバック関数"""
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
        else:
            st.session_state.error_message = f"「{keyword}」は既に追加されています"
    else:
        st.session_state.error_message = "キーワードを入力してください"


def trigger_test_notification():
    """テスト通知を1回だけ実行するコールバック関数"""
    test_product = "テスト用商品（手動テスト）"
    test_url = "https://shopping.bookoff.co.jp"
    if send_webhook_notification(test_product, test_url, force=True):
        st.toast("✅ テスト通知を送信しました")
    else:
        st.toast("❌ テスト通知の送信に失敗しました")


def remove_keyword(keyword: str):
    """キーワードをリストから削除"""
    if keyword in st.session_state.keywords:
        st.session_state.keywords.remove(keyword)
        save_keywords(st.session_state.keywords)
        st.session_state.error_message = None
        return True
    return False


def check_stock(keyword: str) -> Dict:
    """単一キーワードの在庫を確認"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/stock",
            json={"query": keyword},
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "error": True,
                "message": f"エラー: {response.status_code}",
                "detail": response.json().get("detail", "不明なエラー")
            }
    except requests.exceptions.ConnectionError:
        return {
            "error": True,
            "message": "バックエンドサーバーに接続できません",
            "detail": f"{BACKEND_URL} が起動していることを確認してください"
        }
    except Exception as e:
        return {
            "error": True,
            "message": "エラーが発生しました",
            "detail": str(e)
        }


def check_all_keywords():
    """すべてのキーワードの在庫を確認"""
    if not st.session_state.keywords:
        st.session_state.error_message = "キーワードを追加してください"
        return
    
    results = {}
    for keyword in st.session_state.keywords:
        results[keyword] = check_stock(keyword)
    
    st.session_state.stock_results = results
    st.session_state.error_message = None


def process_notifications(force: bool = False):
    """在庫あり商品の通知処理を実行"""
    print("[DEBUG] 通知処理を開始します")
    if not st.session_state.stock_results:
        print("[DEBUG] 在庫検索結果が空のため通知処理をスキップします")
        return

    # 通知判定 (在庫あり)
    in_stock_keywords = [
        k for k, r in st.session_state.stock_results.items()
        if not r.get("error") and r.get("in_stock")
    ]
    print(f"[DEBUG] 在庫あり件数: {len(in_stock_keywords)}")
    
    if in_stock_keywords:
        today_str = datetime.date.today().isoformat()
        
        # 自動検索（force=False）の場合、今日すでに通知済みならスキップ
        # 手動検索（force=True）の場合はこのチェックを無視して送信する
        last_sent_date = st.session_state.settings.get("last_notification_sent_date", "")
        if not force and last_sent_date == today_str:
            print(f"[DEBUG] 本日は既に通知済みのため、自動通知をスキップします (日付: {today_str})")
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
    """一括検索と通知処理を実行（手動・自動共通）"""
    with st.spinner("在庫確認中..."):
        check_all_keywords()
        process_notifications(force=force)


def display_result_card(keyword: str, result: Dict):
    """在庫確認結果をカード形式で表示"""
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
    """メイン処理"""
    initialize_session_state()
    
    # --- 自動検索の実行判定 (描画前) ---
    if st.session_state.auto_loop:
        interval = st.session_state.settings.get("interval_minutes", 60)
        now = datetime.datetime.now()
        should_run = False
        
        if st.session_state.last_run_time is None:
            should_run = True
        else:
            elapsed = (now - st.session_state.last_run_time).total_seconds()
            if elapsed >= interval * 60:
                should_run = True
        
        if should_run:
            if is_within_search_window() and st.session_state.keywords:
                # 自動検索は通常モード (force=False)
                execute_search_batch(force=False)
            st.session_state.last_run_time = now
    
    # ヘッダー
    st.title("📚 BOOKOFF 在庫確認")
    st.markdown("---")
    
    # サイドバー - API接続状態確認
    with st.sidebar:
        st.header("⚙️ 設定")
        
        if st.button("API接続確認"):
            try:
                response = requests.get(f"{BACKEND_URL}/health", timeout=5)
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
            st.button("➕ 追加", use_container_width=True, on_click=add_keyword_callback)
        
        with col2:
            if st.button("🗑️ すべてクリア", use_container_width=True):
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
                    if st.button("❌", key=f"remove_{keyword}", use_container_width=True):
                        remove_keyword(keyword)
                        st.rerun()
        else:
            st.info("キーワードが登録されていません")

        st.markdown("---")
        st.header("⚙️ 自動検索設定")
        
        with st.expander("設定を開く", expanded=False):
            st.session_state.settings["interval_minutes"] = st.number_input(
                "検索間隔 (分)", 
                min_value=1, 
                value=int(st.session_state.settings.get("interval_minutes", 60))
            )
            
            if st.button("💾 設定を保存", use_container_width=True):
                save_settings(st.session_state.settings)
                st.success("設定を保存しました")
    
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
            if st.button("🔎 今すぐ検索", use_container_width=True, type="primary"):
                # 手動検索は強制実行 (force=True)
                execute_search_batch(force=True)
        
        with col_act2:
            if st.session_state.auto_loop:
                st.warning("自動検索中 (停止はリロード)")
            else:
                def start_auto_loop():
                    st.session_state.auto_loop = True
                    st.session_state.last_run_time = None
                
                st.button("🔄 自動検索を開始", use_container_width=True, on_click=start_auto_loop)

        if st.session_state.auto_loop:
            interval = st.session_state.settings.get("interval_minutes", 60)
            st.success(f"🔄 自動検索モードが有効です (実行間隔: {interval}分)")
            
            if not is_within_search_window():
                st.warning(f"現在時間外です。検索は {SEARCH_START_HOUR}:00～{SEARCH_END_HOUR}:00 の間に行われます。")

            # 実行判定 (初回 または 指定時間が経過)
            should_run = False
            now = datetime.datetime.now()
            if st.session_state.last_run_time is None:
                should_run = True
            else:
                elapsed = (now - st.session_state.last_run_time).total_seconds()
                if elapsed >= interval * 60:
                    should_run = True

            # 進行状況表示用のプレースホルダー
            status_container = st.empty()
            st.caption("※ 停止する場合はブラウザをリロードしてください")

    else:
        st.info("📝 左のサイドバーからキーワードを追加してください")
    
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

    # 自動検索モード時の待機処理 (全ての描画が終わった後に行う)
    if st.session_state.auto_loop and st.session_state.last_run_time:
        interval = st.session_state.settings.get("interval_minutes", 60)
        
        # カウントダウンループ（再帰呼び出しによるエラー回避のため、ループ内で待機）
        while True:
            now = datetime.datetime.now()
            elapsed = (now - st.session_state.last_run_time).total_seconds()
            total_sec = interval * 60
            
            if elapsed >= total_sec:
                st.rerun()
                break
            
            # 画面更新
            remaining_sec = max(0, int(total_sec - elapsed))
            progress = min(1.0, max(0.0, elapsed / total_sec))
            
            try:
                status_container.progress(progress, text=f"次回の検索まであと {remaining_sec} 秒")
            except Exception:
                pass
                
            time.sleep(1)


if __name__ == "__main__":
    main()
