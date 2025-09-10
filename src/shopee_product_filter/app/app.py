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
def initialize_price_calculator():
    app_config = load_application_config()
    exchange_provider = ExchangeRateProvider(
        cache_seconds=app_config.api_config.get("exchange_rate_cache_seconds", 3600)
    )
    return PriceCalculator(app_config, exchange_provider)

# --- Main App UI ---
st.set_page_config(layout="wide", page_title="Shopee Product Prospector")
st.title("🛍️ Shopee Product Prospector")
st.info(f"ℹ️ **ご利用の前に、APIサーバーが起動していることを確認してください。** (通常ポート: {FASTAPI_BASE_URL.split(':')[-1]})")

# --- File Upload Section ---
with st.expander("📤 商品一覧HTMLファイルをアップロードしてDBに登録/更新", expanded=True):
    uploaded_html_files = st.file_uploader(
        "Shopeeの商品一覧HTMLファイルを選択してください。", type="html", accept_multiple_files=True, key="html_uploader"
    )
    if uploaded_html_files:
        files_to_upload = [("html_files", (f.name, f.getvalue(), f.type)) for f in uploaded_html_files]
        try:
            with st.spinner(f"{len(files_to_upload)}個のファイルをAPIサーバーに送信中..."):
                response = requests.post(FASTAPI_UPLOAD_URL, files=files_to_upload)
            
            st.subheader("処理結果")
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

        except requests.exceptions.RequestException as e:
            st.error(f"APIサーバーへの接続中にエラーが発生しました: {e}")

# --- DB Search Section ---
st.header("🔍 登録済み商品検索")

# Define columns for selection
ALL_COLUMNS = ["id", "product_url", "product_name", "price", "currency", "image_url", "location", "sold", "shop_type", "list_type", "created_at", "updated_at"]
DEFAULT_COLUMNS = ["product_name", "price", "sold", "shop_type", "list_type", "product_url"]

# Initialize session state
if 'search_results_df' not in st.session_state:
    st.session_state.search_results_df = pd.DataFrame()

with st.form(key="product_search_form"):
    st.subheader("絞り込み条件")
    c1, c2, c3 = st.columns(3)
    with c1:
        min_sold = st.number_input("最小販売数", min_value=0, value=10)
    with c2:
        max_sold = st.number_input("最大販売数", min_value=0, value=1000)
    with c3:
        shop_type = st.selectbox("ショップタイプ", options=["", "Standard", "Preferred", "Mall"], index=0)

    st.subheader("表示オプション")
    col_opt1, col_opt2 = st.columns([3, 1])
    with col_opt1:
        selected_columns = st.multiselect("表示する列を選択", options=ALL_COLUMNS, default=DEFAULT_COLUMNS)
    with col_opt2:
        limit = st.number_input("最大表示件数", min_value=1, max_value=1000, value=50)
    
    search_button = st.form_submit_button(label="この条件で検索")

if search_button:
    params = {
        "min_sold": min_sold,
        "max_sold": max_sold,
        "shop_type": shop_type if shop_type else None,
        "limit": limit
    }
    params = {k: v for k, v in params.items() if v is not None}

    try:
        with st.spinner("データベースから商品情報を検索中..."):
            response = requests.get(FASTAPI_PRODUCTS_URL, params=params)
        
        if response.status_code == 200:
            data = response.json()
            if data:
                st.session_state.search_results_df = pd.DataFrame(data)
            else:
                st.session_state.search_results_df = pd.DataFrame()
                st.info("指定された条件に一致する商品はありませんでした。")
        else:
            st.error(f"APIサーバーからエラーが返されました (ステータスコード: {response.status_code})")
            st.json(response.json())
            st.session_state.search_results_df = pd.DataFrame()

    except requests.exceptions.RequestException as e:
        st.error(f"APIサーバーへの接続中にエラーが発生しました: {e}")
        st.session_state.search_results_df = pd.DataFrame()

# --- Display Search Results and Preview ---
if not st.session_state.search_results_df.empty:
    st.subheader(f"検索結果: {len(st.session_state.search_results_df)} 件")
    
    df_display = st.session_state.search_results_df.copy()
    # Add preview column and filter by user selection
    df_display["プレビュー"] = False
    
    # Ensure selected columns exist in the dataframe
    display_cols = ["プレビュー"] + [col for col in selected_columns if col in df_display.columns]
    
    edited_df = st.data_editor(df_display[display_cols], key="search_results_editor")

    selected_rows = edited_df[edited_df["プレビュー"]]

    if not selected_rows.empty:
        st.subheader(f"{len(selected_rows)}件のプレビュー")
        for index, row_series in selected_rows.iterrows():
            # Get full data for the selected row from the original dataframe
            original_row = st.session_state.search_results_df.loc[index]
            selected_row_dict = original_row.to_dict()
            st.markdown("---")
            col_img, col_info = st.columns([1, 4])
            with col_img:
                if selected_row_dict.get("image_url"):
                    st.image(selected_row_dict["image_url"], width=150)
            with col_info:
                st.markdown(f"**{selected_row_dict.get('product_name', '商品名なし')}**")
                st.text(f"価格: {selected_row_dict.get('price')} {selected_row_dict.get('currency')}")
                st.text(f"販売数: {selected_row_dict.get('sold', 0)}")
                st.text(f"発送元: {selected_row_dict.get('location', '不明')}")
                st.text(f"ショップタイプ: {selected_row_dict.get('shop_type', '不明')}")
                if selected_row_dict.get('product_url'):
                    st.markdown(f"[Shopeeで見る]({selected_row_dict['product_url']})")

# --- Price Calculator Section ---
try:
    calculator = initialize_price_calculator()
    supported_countries = list(calculator.config.countries.keys())
except Exception as e:
    st.error(f"価格計算モジュールの初期化中にエラーが発生しました: {e}")
    st.stop()

with st.expander("🧮 最低仕入れ価格 計算ツール (クリックで展開)"):
    st.markdown("Shopeeでの目標販売価格と商品の重量・サイズから、利益を確保できる仕入れ価格の上限を逆算します。")
    
    with st.form(key="cost_price_form"):
        st.subheader("入力項目")
        col1, col2, col3 = st.columns(3)
        with col1:
            country_code = st.selectbox("販売国", options=supported_countries, index=0)
            target_selling_price_local = st.number_input("目標販売価格 (現地通貨)", min_value=0.0, value=100.0, format="%.2f")
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