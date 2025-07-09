import streamlit as st
import pandas as pd
import requests
import os
import logging # logging モジュールをしっかり使うぜ！
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date
from bs4 import BeautifulSoup

# --- ロギング設定を強化 ---
# Streamlitのルートロガーにハンドラを追加すると、Streamlit自体のログも一緒に出ちゃうことがあるから、
# このアプリ専用のロガーを作るのがオススメだぜ！
logger = logging.getLogger("product_list_streamlit_app")
logger.setLevel(logging.INFO) # ログレベルを設定 (DEBUGにするともっと詳しい情報が出る)
# ハンドラが既に追加されてないか確認 (Streamlitが再実行されるたびに重複して追加されるのを防ぐ)
if not logger.handlers:
    handler = logging.StreamHandler() # コンソールに出力するハンドラ
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# --- FastAPIのエンドポイントURL (変更なし) ---
FASTAPI_PRODUCT_LIST_BASE_URL = "http://127.0.0.1:8002"
FASTAPI_UPLOAD_URL = f"{FASTAPI_PRODUCT_LIST_BASE_URL}/upload-product-list-html/"
FASTAPI_PRODUCTS_URL = f"{FASTAPI_PRODUCT_LIST_BASE_URL}/basic-products/"

# --- 為替レート取得関数 (ログ追加) ---
DUMMY_RATE_SGD_JPY = 110.0
def get_exchange_rate(pair: str, is_dummy: bool = False) -> float:
    logger.info(f"get_exchange_rate呼び出し: pair={pair}, is_dummy={is_dummy}")
    if is_dummy:
        logger.info(f"ダミー為替レートを使用: {pair} = {DUMMY_RATE_SGD_JPY}")
        if pair.upper() == "SGD-JPY": return DUMMY_RATE_SGD_JPY
        elif pair.upper() == "JPY-SGD": return 1 / DUMMY_RATE_SGD_JPY
        else:
            logger.error(f"対応していないダミー通貨ペア: {pair}")
            raise ValueError(f"対応していないダミー通貨ペアです: {pair}")

    logger.info(f"Google Financeから為替レート取得開始: {pair}")
    url = f"https://www.google.com/finance/quote/{pair.upper()}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        rate_element_selectors = ["div.YMlKec.fxKbKc", "div[data-last-price]", "span[jsmodel][data-entity-id]"]
        rate_text = None
        for selector in rate_element_selectors:
            rate_element = soup.select_one(selector)
            if rate_element:
                rate_text = rate_element.get('data-last-price') if selector == "div[data-last-price]" else rate_element.text
                if rate_text:
                    rate_text = rate_text.replace(",", "").strip()
                    if rate_text:
                        logger.info(f"為替レート要素発見 ({selector}): '{rate_text}'")
                        parsed_rate = float(rate_text)
                        logger.info(f"為替レート取得成功: {pair} = {parsed_rate}")
                        return parsed_rate
        logger.error(f"為替レートの要素が見つかりませんでした: {pair} (URL: {url})")
        raise ValueError(f"為替レートの要素が見つかりませんでした: {pair}")
    except requests.exceptions.RequestException as e:
        logger.error(f"為替レート取得中にリクエストエラー ({pair}): {e}")
        raise ValueError(f"為替レート取得中にリクエストエラーが発生しました: {pair} ({e})")
    except ValueError as e:
        logger.error(f"為替レートの解析/変換失敗 ({pair}): {e}")
        raise ValueError(f"為替レートの解析または変換に失敗しました: {pair} ({e})")
    except Exception as e:
        logger.error(f"為替レート取得中に予期せぬエラー ({pair}): {e}", exc_info=True)
        raise ValueError(f"為替レート取得中に予期せぬエラーが発生しました: {pair} ({e})")

# Streamlit アプリのページ設定 (変更なし)
st.set_page_config(layout="wide", page_title="Shopee 商品リスト情報管理")
st.title("🛍️ Shopee 商品リスト情報 管理システム")
st.markdown("商品一覧HTMLから基本情報を抽出し、データベースに登録・検索できます。")
st.info("ℹ️ **ご利用の前に、商品リスト情報APIサーバーが起動していることを確認してください。** (通常はポート8002)")

# --- ファイルアップロードセクション (ログ追加) ---
with st.expander("📤 商品リストHTMLファイルをアップロードしてDBに登録"):
    uploaded_html_files = st.file_uploader(
        "Shopeeの商品一覧HTMLファイルを選択してください。", type="html", accept_multiple_files=True,
        help="複数のHTMLファイルを一度にアップロードできます...", key="product_list_html_uploader"
    )
    if uploaded_html_files:
        logger.info(f"{len(uploaded_html_files)}個のHTMLファイルがアップロードされました。")
        st.info(f"{len(uploaded_html_files)}個のファイルをAPIサーバーに送信します。")
        # (progress_bar と status_text はUI用なのでログは省略)
        files_to_send = []
        for i, uploaded_file in enumerate(uploaded_html_files):
            logger.info(f"  アップロードファイル {i+1}: {uploaded_file.name} (サイズ: {uploaded_file.size} bytes, タイプ: {uploaded_file.type})")
            files_to_send.append(('html_files', (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)))

        if files_to_send:
            try:
                logger.info(f"FastAPIエンドポイント '{FASTAPI_UPLOAD_URL}' にファイルを送信します。")
                response = requests.post(FASTAPI_UPLOAD_URL, files=files_to_send)
                logger.info(f"FastAPIからのレスポンスステータス: {response.status_code}")
                response.raise_for_status()
                result = response.json()
                logger.info(f"FastAPIからのレスポンスボディ (JSON): {result}")
                st.subheader("アップロード処理結果")
                st.json(result)
                if result.get("processed_files", 0) > 0: st.success(f"{result.get('processed_files')} 個のファイルの処理に成功しました。")
                if result.get("skipped_files_or_parse_errors", 0) > 0: st.warning(f"{result.get('skipped_files_or_parse_errors')} 個のファイルでエラー/スキップ発生。詳細はJSON結果やログ参照。")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"FastAPI接続エラー (アップロード時): {e}")
                st.error("🚨 APIサーバーに接続できませんでした。")
            except requests.exceptions.HTTPError as e:
                logger.error(f"FastAPI HTTPエラー (アップロード時): ステータス={e.response.status_code}, レスポンス={e.response.text}")
                st.error(f"🚨 APIサーバーからエラー ({e.response.status_code}): {e.response.text}")
            except Exception as e:
                logger.error(f"ファイルアップロード処理中の予期せぬエラー: {e}", exc_info=True)
                st.error(f"🚨 アップロード処理中にエラー: {e}")

# --- DBから商品リスト情報を検索・表示するセクション (ログ追加) ---
st.header("🔍 データベース内の商品リスト情報を検索・表示")

ALL_PRODUCT_LIST_COLUMNS = ["id", "product_url", "created_at", "product_name", "price", "currency", "image_url", "location", "sold", "shop_type", "list_type"]
DEFAULT_PRODUCT_LIST_DISPLAY_COLUMNS = ["product_name", "price", "currency", "sold", "location", "shop_type", "list_type", "image_url"]

# 為替レートの取得と表示 (ログはget_exchange_rate関数内に追加済み)
if 'sgd_to_jpy_rate' not in st.session_state: st.session_state.sgd_to_jpy_rate = None
if 'jpy_to_sgd_rate' not in st.session_state: st.session_state.jpy_to_sgd_rate = None

if st.button("現在のSGD-JPY為替レートを更新", key="update_rate_button"):
    try:
        st.session_state.sgd_to_jpy_rate = get_exchange_rate("SGD-JPY", is_dummy=False) # 本番用
        st.session_state.jpy_to_sgd_rate = 1 / st.session_state.sgd_to_jpy_rate
        st.success(f"現在の為替レート: 1 SGD = {st.session_state.sgd_to_jpy_rate:.2f} JPY")
        logger.info(f"為替レート更新成功: 1 SGD = {st.session_state.sgd_to_jpy_rate:.2f} JPY")
    except ValueError as e:
        st.error(f"為替レートの取得に失敗: {e}")
        st.session_state.sgd_to_jpy_rate = None
        st.session_state.jpy_to_sgd_rate = None
        logger.warning(f"為替レート更新失敗: {e}")

if st.session_state.sgd_to_jpy_rate: st.caption(f"現在のSGD-JPYレート (参考): 1 SGD = {st.session_state.sgd_to_jpy_rate:.2f} JPY")
else: st.warning("SGD-JPY為替レートが未取得です。価格検索（JPY）の精度に影響する可能性があります。")

with st.form(key="product_list_search_form"):
    st.subheader("絞り込み条件")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**価格 (日本円で入力)**")
        min_price_jpy = st.number_input("最小価格 (JPY)", min_value=0, value=None, placeholder="例: 5000", key="pl_min_jpy")
        max_price_jpy = st.number_input("最大価格 (JPY)", min_value=0, value=None, placeholder="例: 30000", key="pl_max_jpy")
    with c2:
        st.markdown("**販売数**")
        min_sold = st.number_input("最小販売数", min_value=0, value=None, placeholder="例: 3", key="pl_min_sold")
        max_sold = st.number_input("最大販売数", min_value=0, value=None, placeholder="例: 100", key="pl_max_sold")
    st.markdown("**オプション**")
    c3, c4 = st.columns(2)
    with c3:
        location_japan_only = st.checkbox("配送元が日本の商品のみ", value=False, key="pl_loc_jp")
        shop_types = st.multiselect("ショップタイプ", options=["Standard", "Preferred", "Mall", "Official Store"], default=[], key="pl_shop_types")
    with c4:
        list_types = st.multiselect("リストタイプ", options=["ショップ", "検索/カテゴリー", "汎用", "不明"], default=[], key="pl_list_types")
    enable_date_filter = st.checkbox("登録日でフィルタリングする", key="pl_enable_date_filter")
    start_date_val: Optional[datetime] = None
    end_date_val: Optional[datetime] = None
    if enable_date_filter:
        col_date1, col_date2 = st.columns(2)
        with col_date1:
            d_start = st.date_input("登録日 (開始日)", value=date.today(), key="pl_d_start")
            if d_start: start_date_val = datetime.combine(d_start, datetime.min.time())
        with col_date2:
            d_end = st.date_input("登録日 (終了日)", value=date.today(), key="pl_d_end")
            if d_end: end_date_val = datetime.combine(d_end, datetime.max.time())
    st.subheader("表示オプション")
    selected_columns_to_display = st.multiselect(
        "検索結果テーブル表示項目:", options=ALL_PRODUCT_LIST_COLUMNS, default=DEFAULT_PRODUCT_LIST_DISPLAY_COLUMNS, key="pl_display_cols"
    )
    # ページネーションのための表示開始位置
    display_start_index = st.number_input("表示開始位置 (ページネーション用)", min_value=0, value=0, step=10, key="pl_offset")
    display_limit = st.number_input("最大表示件数 (リミット)", min_value=1, max_value=200, value=50, step=10, key="pl_limit")
    search_button = st.form_submit_button(label="この条件で検索")

if search_button:
    logger.info("検索ボタンがクリックされました。")
    # --- フォーム入力値のログ ---
    form_inputs = {
        "min_price_jpy": min_price_jpy, "max_price_jpy": max_price_jpy,
        "min_sold": min_sold, "max_sold": max_sold,
        "location_japan_only": location_japan_only,
        "shop_types": shop_types, "list_types": list_types,
        "enable_date_filter": enable_date_filter,
        "start_date_input (form)": start_date_val.isoformat() if start_date_val else None,
        "end_date_input (form)": end_date_val.isoformat() if end_date_val else None,
        "selected_columns_to_display": selected_columns_to_display,
        "offset": display_start_index, "limit": display_limit
    }
    logger.info(f"検索フォーム入力値: {form_inputs}")

    search_params_api: Dict[str, Any] = {"offset": display_start_index, "limit": display_limit}
    min_price_sgd_val: Optional[float] = None
    max_price_sgd_val: Optional[float] = None
    if st.session_state.jpy_to_sgd_rate:
        if min_price_jpy is not None:
            min_price_sgd_val = float(min_price_jpy) * st.session_state.jpy_to_sgd_rate
            search_params_api["min_price_sgd"] = min_price_sgd_val
        if max_price_jpy is not None:
            max_price_sgd_val = float(max_price_jpy) * st.session_state.jpy_to_sgd_rate
            search_params_api["max_price_sgd"] = max_price_sgd_val
    elif min_price_jpy is not None or max_price_jpy is not None:
        st.warning("為替レート未取得のため、JPY価格検索は行われません。")
        logger.warning("為替レート未取得のため、JPY価格でのフィルタリングはスキップされました。")

    if min_sold is not None: search_params_api["min_sold"] = min_sold
    if max_sold is not None: search_params_api["max_sold"] = max_sold
    if location_japan_only: search_params_api["location_keywords"] = "Japan"
    if shop_types: search_params_api["shop_types"] = shop_types
    if list_types: search_params_api["list_types"] = list_types
    if enable_date_filter and start_date_val: search_params_api["start_date"] = start_date_val.isoformat()
    if enable_date_filter and end_date_val: search_params_api["end_date"] = end_date_val.isoformat()
        
    st.markdown("---"); st.subheader("現在の検索条件 (API送信値)")
    active_search_filters_api = {k: v for k, v in search_params_api.items() if v is not None and k not in ["offset", "limit"]}
    if active_search_filters_api: st.json(active_search_filters_api)
    else: st.info("絞り込み条件なし。")
    
    # --- FastAPIへのリクエストパラメータのログ ---
    logger.info(f"FastAPIへの検索リクエストパラメータ: {search_params_api}")

    with st.spinner("商品リスト情報をデータベースから検索中です..."):
        try:
            response = requests.get(FASTAPI_PRODUCTS_URL, params=search_params_api)
            logger.info(f"FastAPIからの検索レスポンスステータス: {response.status_code}")
            response.raise_for_status()
            searched_data = response.json()
            # --- FastAPIからのレスポンス概要のログ ---
            logger.info(f"FastAPIからの検索レスポンス件数: {len(searched_data)}")
            if searched_data: logger.debug(f"FastAPIからの検索レスポンスデータ (最初の1件): {searched_data[0] if searched_data else 'N/A'}") # DEBUGレベルで最初の1件だけ
            
            if searched_data:
                df_searched = pd.DataFrame(searched_data)
                st.subheader(f"検索結果: {len(df_searched)} 件の商品が見つかりました")
                if selected_columns_to_display:
                    cols_to_show = [col for col in selected_columns_to_display if col in df_searched.columns]
                    if cols_to_show:
                        df_display = df_searched[cols_to_show].copy()
                        if 'image_url' in df_display.columns:
                            # 画像表示は st.data_editor を使う (Streamlit 1.20.0以降)
                            if hasattr(st, "data_editor"):
                                st.data_editor(
                                    df_display,
                                    column_config={"image_url": st.column_config.ImageColumn("商品画像", help="サムネイル")},
                                    use_container_width=True, hide_index=True
                                )
                            else:
                                st.markdown("画像表示にはStreamlit 1.20.0以上が必要です。URLを表示します。")
                                st.dataframe(df_searched[cols_to_show], use_container_width=True)
                        else:
                             st.dataframe(df_searched[cols_to_show], use_container_width=True)
                    else:
                         st.warning("選択された表示項目が検索結果データにありませんでした。"); st.dataframe(df_searched, use_container_width=True)
                else:
                    st.info("表示項目未選択のため全項目表示します。"); st.dataframe(df_searched, use_container_width=True)

                col_dl_pl1, col_dl_pl2 = st.columns(2)
                with col_dl_pl1: st.download_button("検索結果をCSVでダウンロード", df_searched.to_csv(index=False).encode('utf-8'), "s_searched_pl.csv", "text/csv", key="dl_pl_csv", use_container_width=True)
                with col_dl_pl2: st.download_button("検索結果をJSONでダウンロード", df_searched.to_json(orient="records", indent=4).encode('utf-8'), "s_searched_pl.json", "application/json", key="dl_pl_json", use_container_width=True)
                st.markdown("---"); st.subheader("商品リストアイテム詳細 (全項目)")
                for _, row in df_searched.iterrows():
                    item_id = row.get('id', 'ID不明'); item_name = row.get('product_name', '商品名不明')
                    with st.expander(f"ID: {item_id} - {item_name[:60]}{'...' if len(str(item_name)) > 60 else ''}"):
                        if row.get('image_url'): st.image(row['image_url'], caption=item_name, width=150)
                        st.json(row.to_dict())
                        if row.get('product_url'): st.markdown(f"**商品URL:** [{row['product_url']}]({row['product_url']})")
            else:
                st.info("指定条件に一致する商品リスト情報は見つかりませんでした。")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"FastAPI接続エラー (検索時): {e}")
            st.error("🚨 APIサーバーに接続できませんでした。")
        except requests.exceptions.HTTPError as e:
            logger.error(f"FastAPI HTTPエラー (検索時): ステータス={e.response.status_code}, レスポンス={e.response.text}")
            st.error(f"🚨 APIサーバーからエラー ({e.response.status_code}): {e.response.text}")
        except Exception as e:
            logger.error(f"商品リスト情報検索中の予期せぬエラー: {e}", exc_info=True)
            st.error(f"🚨 検索中にエラー: {e}")
else:
    st.info("上記のフォームに条件を入力し、「この条件で検索」ボタンを押すと、DBから商品リスト情報が検索されます。")

