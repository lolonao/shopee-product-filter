import streamlit as st
import pandas as pd
import requests
import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import sys
from pathlib import Path
import json
import time

# --- モジュール検索パスの設定 ---
# 'uv run streamlit run' で実行した際に 'src' 配下のモジュールを正しく見つけられるように、
# プロジェクトの 'src' ディレクトリをsys.pathに追加します。
# これにより、`shopee_price_pilot`のようなベンダー化されたライブラリをインポート可能にします。
try:
    # 現在のファイルの絶対パスからプロジェクトルートを特定
    # (shopee-product-filter/src/shopee_product_filter/app/app.py)
    # 3階層上がプロジェクトルート
    project_root = Path(__file__).resolve().parents[3]
    src_path = project_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
except IndexError:
    # ファイル構造が予期したものと異なる場合のエラーハンドリング
    # スクリプトがプロジェクトルート直下などで実行された場合を想定
    src_path = Path("./src").resolve()
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


# --- Vendored Library Imports ---
from shopee_price_pilot.models import AppConfig, CountrySettings
from shopee_price_pilot.exchange import ExchangeRateProvider
from shopee_price_pilot.calculator import PriceCalculator
from shopee_price_pilot.data_loader import load_application_config

# --- App Constants ---
FASTAPI_BASE_URL = "http://127.0.0.1:8002"
FASTAPI_UPLOAD_URL = f"{FASTAPI_BASE_URL}/upload-product-list-html/"
FASTAPI_PRODUCTS_URL = f"{FASTAPI_BASE_URL}/basic-products/"

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

# --- Data Loading and Initialization ---
@st.cache_resource
def initialize_exchange_rate_provider():
    """為替レートプロバイダーを初期化してキャッシュする"""
    app_config = load_application_config()
    return ExchangeRateProvider(
        cache_seconds=app_config.api_config.get("exchange_rate_cache_seconds", 3600)
    )

@st.cache_resource
def initialize_price_calculator():
    app_config = load_application_config()
    exchange_provider = initialize_exchange_rate_provider()
    return PriceCalculator(app_config, exchange_provider)

# --- コールバック関数 ---
def set_calculator_inputs(price: float, currency: str):
    """プレビュー欄のボタンが押されたときに、計算機の入力値をセッション状態で更新し、エキスパンダーを開く"""
    st.session_state.target_price = price
    # 通貨から国コードを取得し、セッション状態を更新
    country_code = CURRENCY_TO_COUNTRY.get(currency)
    if country_code:
        st.session_state.target_country_code = country_code
    st.session_state.calculator_expanded = True # 計算機エキスパンダーを開かせる

def clear_upload_state():
    """ファイルアップローダーの内容が変更されたときに、処理済みフラグをリセットする"""
    if 'upload_processed' in st.session_state:
        st.session_state.upload_processed = False

# --- Main App UI ---
st.set_page_config(layout="wide", page_title="Shopee Product Prospector")
st.title("🛍️ Shopee Product Prospector")
st.info(f"ℹ️ **ご利用の前に、APIサーバーが起動していることを確認してください。** (通常ポート: {FASTAPI_BASE_URL.split(':')[-1]})")

# --- File Upload Section ---
with st.expander("📤 商品一覧HTMLファイルをアップロードしてDBに登録/更新", expanded=True):
    uploaded_html_files = st.file_uploader(
        "Shopeeの商品一覧HTMLファイルを選択してください。",
        type="html",
        accept_multiple_files=True,
        key="html_uploader",
        on_change=clear_upload_state
    )
    # ファイルがアップロードされ、まだ処理されていない場合にのみ実行
    if uploaded_html_files and not st.session_state.get("upload_processed", False):
        files_to_upload = [("html_files", (f.name, f.getvalue(), f.type)) for f in uploaded_html_files]
        try:
            with st.spinner(f"{len(files_to_upload)}個のファイルをAPIサーバーに送信中..."):
                response = requests.post(FASTAPI_UPLOAD_URL, files=files_to_upload)
            
            st.subheader("処理結果")
            # メッセージ表示用のプレースホルダー
            placeholder = st.empty()
            with placeholder.container():
                if response.status_code == 200:
                    results = response.json()
                    for result in results:
                        file_name = result.get("file_name", "不明なファイル")
                        status = result.get("status", "unknown")
                        message = result.get("message", "詳細不明")
                        if status == "success":
                            st.success(f"✅ {file_name}: {message}")
                        elif status == "skipped":
                            st.warning(f"⚠️ {file_name}: {message}")
                        else:
                            st.error(f"❌ {file_name}: {message}")
                else:
                    st.error(f"APIサーバーからエラーが返されました (ステータスコード: {response.status_code})")
                    try:
                        st.json(response.json())
                    except json.JSONDecodeError:
                        st.text(response.text)

            # 5秒待ってからメッセージを消去
            time.sleep(5)
            placeholder.empty()

        except requests.exceptions.RequestException as e:
            placeholder = st.empty()
            with placeholder.container():
                st.error(f"APIサーバーへの接続中にエラーが発生しました: {e}")
            time.sleep(5)
            placeholder.empty()

        # 処理が完了したことをマーク
        st.session_state.upload_processed = True

# --- DB Search Section ---
st.header("🔍 登録済み商品検索")

# --- 為替レートの取得 ---
# 初期化関数を呼び出して、キャッシュされたプロバイダーインスタンスを取得
exchange_provider = initialize_exchange_rate_provider()
# シンガポールドルから日本円への為替レートを取得
sgd_jpy_rate = exchange_provider.get_rate("SGD-JPY")
if sgd_jpy_rate:
    st.sidebar.success(f"現在の為替レート: 1 SGD ≈ {sgd_jpy_rate:.2f} JPY")
else:
    st.sidebar.error("為替レートの取得に失敗しました。価格フィルタリングと表示が不正確になる可能性があります。")
    # フォールバックとして固定レートを設定することも可能
    # sgd_jpy_rate = 110.0

# --- UI表示設定 ---
# DBカラム名と日本語表示名のマッピング
# created_at, updated_at はUTCで保存されているため、ユーザーには分かりやすいようにタイムゾーン情報を付記
COLUMN_MAPPING = {
    "id": "商品ID",
    "product_url": "商品URL",
    "product_name": "商品名",
    "price": "価格 (SGD)",
    "price_jpy": "価格 (JPY)", # JPY価格表示用の列を追加
    "currency": "通貨",
    "image_url": "画像URL",
    "location": "発送元",
    "sold": "販売数",
    "shop_type": "ショップタイプ",
    "list_type": "リストタイプ",
    "created_at": "登録日時 (UTC)",
    "updated_at": "最終更新日時 (UTC)"
}

# デフォルトで表示する列のリスト（日本語表示名）
# JPY価格もデフォルトで表示するように変更
DEFAULT_DISPLAY_COLUMNS = ["商品名", "価格 (SGD)", "価格 (JPY)", "販売数", "発送元", "ショップタイプ", "リストタイプ", "画像URL", "商品URL"]

# 利用可能な全ての列リスト（日本語表示名）
ALL_DISPLAY_COLUMNS = list(COLUMN_MAPPING.values())

# 通貨コードとPricePilotの国コードのマッピング
CURRENCY_TO_COUNTRY = {
    "SGD": "SG",
    "PHP": "PH",
}


# Initialize session state
if 'search_results_df' not in st.session_state:
    st.session_state.search_results_df = pd.DataFrame()
if 'upload_processed' not in st.session_state:
    st.session_state.upload_processed = False
# プレビューから計算機に値を渡すためのセッション状態
if 'target_price' not in st.session_state:
    st.session_state.target_price = 100.0  # 計算機のデフォルト値
if 'target_country_code' not in st.session_state:
    st.session_state.target_country_code = "SG"  # デフォルトはシンガポール
if 'calculator_expanded' not in st.session_state:
    st.session_state.calculator_expanded = False # 計算機エキスパンダーの開閉状態


with st.form(key="product_search_form", enter_to_submit=False):
    st.subheader("絞り込み条件")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        min_sold = st.number_input("最小販売数", min_value=0, value=10)
    with c2:
        max_sold = st.number_input("最大販売数", min_value=0, value=1000)
    with c3:
        # JPYでの価格範囲入力フォームを追加
        min_price_jpy = st.number_input("最小価格 (JPY)", min_value=0, value=0)
    with c4:
        max_price_jpy = st.number_input("最大価格 (JPY)", min_value=0, value=0)

    # 2段目の絞り込み条件
    c5, c6, c7, c8 = st.columns(4)
    with c5:
        shop_type = st.selectbox("ショップタイプ", options=["", "Standard", "Preferred", "Mall"], index=0)


    st.subheader("表示オプション")
    col_opt1, col_opt2 = st.columns([3, 1])
    with col_opt1:
        # 日本語の表示名で列を選択できるようにする
        selected_display_columns = st.multiselect(
            "表示する列を選択",
            options=ALL_DISPLAY_COLUMNS,
            default=DEFAULT_DISPLAY_COLUMNS
        )
    with col_opt2:
        limit = st.number_input("最大表示件数", min_value=1, max_value=1000, value=50)
    
    search_button = st.form_submit_button(label="この条件で検索")

if search_button:
    # --- 入力値のバリデーション ---
    error_messages = []
    # 最小価格が最大価格を上回っていないかチェック
    # max_price_jpy > 0 の条件は、最大価格が入力されている場合のみチェックするため
    if max_price_jpy > 0 and min_price_jpy > max_price_jpy:
        error_messages.append("価格設定エラー: 最大価格は最小価格以上の値を入力してください。")

    # 最小販売数が最大販売数を上回っていないかチェック
    if min_sold > max_sold:
        error_messages.append("販売数エラー: 最大販売数は最小販売数以上の値を入力してください。")

    # バリデーションエラーがある場合、エラーメッセージを表示し、以前の検索結果をクリア
    if error_messages:
        placeholder = st.empty()
        with placeholder.container():
            for msg in error_messages:
                st.error(msg)

        # 3秒待ってからメッセージを消去
        time.sleep(3)
        placeholder.empty()

        # 以前の検索結果をクリアすることで、エラーメッセージのみが表示されるようにする
        st.session_state.search_results_df = pd.DataFrame()
    # バリデーションエラーがなければ、検索処理を実行
    else:
        params = {
            "min_sold": min_sold,
            "max_sold": max_sold,
            "shop_type": shop_type if shop_type else None,
            "limit": limit
        }
        # JPY価格フィルタのロジック
        if sgd_jpy_rate and (min_price_jpy > 0 or max_price_jpy > 0):
            if min_price_jpy > 0:
                params["min_price_sgd"] = min_price_jpy / sgd_jpy_rate
            if max_price_jpy > 0:
                params["max_price_sgd"] = max_price_jpy / sgd_jpy_rate

        params = {k: v for k, v in params.items() if v is not None}

        try:
            with st.spinner("データベースから商品情報を検索中..."):
                response = requests.get(FASTAPI_PRODUCTS_URL, params=params)
        
            if response.status_code == 200:
                data = response.json()
                if data:
                    df = pd.DataFrame(data)
                    # JPY価格を計算して列を追加
                    if sgd_jpy_rate:
                        # 'price' 列が数値型であることを確認し、NaNの場合は0に置換
                        df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0)
                        df["price_jpy"] = (df["price"] * sgd_jpy_rate).round(0).astype(int)
                    else:
                        df["price_jpy"] = 0 # レート取得失敗時は0
                    st.session_state.search_results_df = df
                else:
                    st.session_state.search_results_df = pd.DataFrame()
                    st.info("指定された条件に一致する商品はありませんでした。")
            else:
                st.error(f"APIサーバーからエラーが返されました (ステータスコード: {response.status_code})")
                try:
                    st.json(response.json())
                except json.JSONDecodeError:
                    st.text(response.text)
                st.session_state.search_results_df = pd.DataFrame()

        except requests.exceptions.RequestException as e:
            st.error(f"APIサーバーへの接続中にエラーが発生しました: {e}")
            st.session_state.search_results_df = pd.DataFrame()

# --- Display Search Results and Preview ---
if not st.session_state.search_results_df.empty:
    st.subheader(f"検索結果: {len(st.session_state.search_results_df)} 件")
    
    # 選択された表示名に対応するDBカラム名を取得
    # 逆マッピングを作成
    REVERSE_COLUMN_MAPPING = {v: k for k, v in COLUMN_MAPPING.items()}
    selected_db_columns = [REVERSE_COLUMN_MAPPING[disp_col] for disp_col in selected_display_columns if disp_col in REVERSE_COLUMN_MAPPING]

    # 表示用のデータフレームを準備
    # JPY価格列が追加されたデータフレームをコピー
    df_display = st.session_state.search_results_df.copy()

    # プレビュー選択用の列を追加
    df_display["プレビュー"] = False
    
    # データを表示する前に、カラム名を日本語に変換
    df_renamed = df_display.rename(columns=COLUMN_MAPPING)

    # 表示する列（日本語名）を決定
    # プレビュー列と、ユーザーが選択した表示列リスト
    display_cols_japanese = ["プレビュー"] + selected_display_columns

    # 存在しない列が選択されてもエラーにならないようにフィルタリング
    final_display_cols = [col for col in display_cols_japanese if col in df_renamed.columns]

    # st.data_editor を使用して、日本語化されたデータフレームを表示
    edited_df_japanese = st.data_editor(
        df_renamed[final_display_cols],
        key="search_results_editor",
        disabled=[col for col in final_display_cols if col != "プレビュー"],
        column_config={
            "プレビュー": st.column_config.CheckboxColumn(
                help="計算ツールに価格を連携したい商品を選択します",
                width="small"
            ),
        },
    )

    # プレビューが選択された行を特定 (日本語の列名で判定)
    selected_rows_japanese = edited_df_japanese[edited_df_japanese["プレビュー"]]

    if not selected_rows_japanese.empty:
        # 日本語のデータフレームのインデックスは元のデータフレームのインデックスと一致する
        selected_indices = selected_rows_japanese.index

        st.subheader(f"{len(selected_indices)}件のプレビュー")
        # 元のデータフレームからプレビュー対象の行を取得
        for index in selected_indices:
            selected_row_dict = st.session_state.search_results_df.loc[index].to_dict()

            st.markdown("---")
            col_img, col_info = st.columns([1, 4])
            with col_img:
                if selected_row_dict.get("image_url"):
                    st.image(selected_row_dict["image_url"], width=150)
            with col_info:
                st.markdown(f"**{selected_row_dict.get('product_name', '商品名なし')}**")
                price_sgd = selected_row_dict.get('price', 0)
                price_jpy = selected_row_dict.get('price_jpy', 0)
                currency = selected_row_dict.get('currency', 'SGD')
                # JPY価格が計算されている場合、両方の価格を表示
                if price_jpy > 0:
                    st.text(f"価格: {price_sgd} {currency} ({price_jpy:,.0f} JPY)")
                else:
                    st.text(f"価格: {price_sgd} {currency}")
                st.text(f"販売数: {selected_row_dict.get('sold', 0)}")
                st.text(f"発送元: {selected_row_dict.get('location', '不明')}")
                st.text(f"ショップタイプ: {selected_row_dict.get('shop_type', '不明')}")
                if selected_row_dict.get('product_url'):
                    st.markdown(f"[Shopeeで見る]({selected_row_dict['product_url']})")

                # --- プレビューから計算ツールへ値を渡すボタン ---
                price = selected_row_dict.get('price', 0.0)
                currency = selected_row_dict.get('currency', '')

                # 対応通貨の場合のみボタンを表示
                if currency in CURRENCY_TO_COUNTRY:
                    st.button(
                        "この価格で仕入れ価格を計算",
                        key=f"calc_btn_{selected_row_dict['id']}",
                        on_click=set_calculator_inputs,
                        args=(price, currency)
                    )

    # --- CSVダウンロード機能 ---
    st.markdown("---")

    # ダウンロード対象の列（日本語名）を決定（プレビュー列は除外）
    download_cols_japanese = [col for col in final_display_cols if col != "プレビュー"]

    # 日本語名に変換済みのデータフレームから、ダウンロード対象の列を抽出
    df_download = df_renamed[download_cols_japanese]

    # to_csvでBOM付きUTF-8にエンコードし、Excelでの文字化けを防ぐ
    csv_data = df_download.to_csv(index=False).encode('utf-8-sig')

    st.download_button(
        label="表示中の列をCSVでダウンロード",
        data=csv_data,
        file_name=f"shopee_products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime='text/csv',
    )


# --- Price Calculator Section ---
try:
    calculator = initialize_price_calculator()
    supported_countries = list(calculator.config.countries.keys())
except Exception as e:
    st.error(f"価格計算モジュールの初期化中にエラーが発生しました: {e}")
    st.stop()

with st.expander("🧮 最低仕入れ価格 計算ツール (クリックで展開)", expanded=st.session_state.calculator_expanded):
    st.markdown("Shopeeでの目標販売価格と商品の重量・サイズから、利益を確保できる仕入れ価格の上限を逆算します。")
    
    with st.form(key="cost_price_form"):
        st.subheader("入力項目")
        col1, col2, col3 = st.columns(3)
        with col1:
            # セッション状態から国コードのデフォルトインデックスを決定
            country_index = supported_countries.index(st.session_state.target_country_code) if st.session_state.target_country_code in supported_countries else 0
            country_code = st.selectbox("販売国", options=supported_countries, index=country_index)

            # セッション状態から目標販売価格のデフォルト値を設定
            target_selling_price_local = st.number_input(
                "目標販売価格 (現地通貨)",
                min_value=0.0,
                value=st.session_state.target_price,
                format="%.2f"
            )
            weight_kg = st.number_input("想定重量 (kg)", min_value=0.0, value=0.5, step=0.05, format="%.2f")
        with col2:
            domestic_shipping = st.number_input("国内送料 (円)", min_value=0, value=710)
            profit_rate = st.slider("欲しい利益率 (%)", 0, 100, 15)
            voucher_rate = st.slider("バウチャー・セール用追加利益率 (%)", 0, 50, 10)
        with col3:
            is_rebate = (st.radio("送料設定", options=["リベート有", "送料無料"]) == "リベート有")
            st.markdown("**商品サイズ (cm) - 任意**")
            length_cm = st.number_input("縦", min_value=0.0, value=0.0, step=0.1, format="%.1f")
            width_cm = st.number_input("横", min_value=0.0, value=0.0, step=0.1, format="%.1f")
            height_cm = st.number_input("高さ", min_value=0.0, value=0.0, step=0.1, format="%.1f")

        calculate_button = st.form_submit_button(label="最低仕入れ価格を計算する")

    if calculate_button:
        with st.spinner("計算中..."):
            result = calculator.calculate_cost_price(
                country_code=country_code,
                target_selling_price_local=float(target_selling_price_local),
                weight_kg=float(weight_kg),
                domestic_shipping=float(domestic_shipping),
                profit_rate=float(profit_rate),
                voucher_rate=float(voucher_rate),
                is_rebate=is_rebate,
                length_cm=float(length_cm),
                width_cm=float(width_cm),
                height_cm=float(height_cm),
            )

        if result.get("error"):
            st.error(f"計算エラー: {result['error']}")
        else:
            st.subheader("🎯 計算結果")
            res_col1, res_col2 = st.columns(2)
            res_col1.metric(label="最低仕入れ価格 (JPY)", value=f"{result['max_cost_price_jpy']:,.0f} 円")
            res_col2.metric(label=f"最低仕入れ価格 ({result['inputs']['country_code']})", value=f"{result['max_cost_price_local']:.2f}")
            with st.expander("計算の内訳詳細"):
                st.json(result)