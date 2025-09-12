import streamlit as st
import pandas as pd
import requests
import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import sys

# calculator.py を同じディレクトリからインポート
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from calculator import calculate_minimum_purchase_price, get_exchange_rate as get_calc_exchange_rate
except ImportError:
    st.error("エラー: `calculator.py` が見つかりません。このアプリと同じディレクトリに配置してください。")
    def calculate_minimum_purchase_price(price, weight):
        raise NotImplementedError("calculator.py がロードできませんでした。")
    def get_calc_exchange_rate(pair, isDummy=False):
        raise NotImplementedError("calculator.py がロードできませんでした。")

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

# --- FastAPIエンドポイントURL ---
FASTAPI_PRODUCT_LIST_BASE_URL = "http://127.0.0.1:8002"
FASTAPI_UPLOAD_PRODUCT_LIST_URL = f"{FASTAPI_PRODUCT_LIST_BASE_URL}/upload-product-list-html/"
FASTAPI_BASIC_PRODUCTS_URL = f"{FASTAPI_PRODUCT_LIST_BASE_URL}/basic-products/"
# ソーシング情報更新用エンドポイントのテンプレート
FASTAPI_SOURCING_INFO_URL_TEMPLATE = f"{FASTAPI_PRODUCT_LIST_BASE_URL}/basic-products/{{item_id}}/sourcing-info"


# --- 為替レート関連 ---
DEFAULT_SGD_TO_JPY_RATE_DISPLAY = 112.0
EXCHANGE_RATE_CACHE_DURATION_SECONDS = 3600

# Streamlit アプリのページ設定
st.set_page_config(layout="wide", page_title="Shopee 商品リスト・ソーシング管理")

st.title("🛍️ Shopee 商品リスト・ソーシング管理アプリ")
st.markdown("商品一覧HTMLの管理、DB検索、最低仕入れ価格計算、そしてソーシング状況の記録ができます。")
st.info(f"ℹ️ **ご利用の前に、商品リスト情報APIサーバーが起動していることを確認してください。** (通常はポート {FASTAPI_PRODUCT_LIST_BASE_URL.split(':')[-1]})")

# --- ソーシングステータスの選択肢 ---
SOURCING_STATUS_OPTIONS = ["", "未着手", "調査中", "仕入先発見", "見つからず", "保留"] # 空文字は「指定なし」または「クリア」

# --- 為替レート取得・キャッシュ関数 (表示用) ---
def get_cached_exchange_rate_for_display(target_currency: str = "JPY", base_currency: str = "SGD") -> Tuple[Optional[float], str]:
    # (内容は前回と同じなので省略)
    cache_key_rate = f"display_exchange_rate_{base_currency.lower()}_{target_currency.lower()}"
    cache_key_time = f"display_exchange_rate_last_updated_{base_currency.lower()}_{target_currency.lower()}"
    rate = None
    source_message = f"デフォルトレート (表示用, {base_currency}-{target_currency})"
    if cache_key_rate in st.session_state and cache_key_time in st.session_state:
        last_updated_time = st.session_state[cache_key_time]
        if isinstance(last_updated_time, datetime) and \
           (datetime.utcnow() - last_updated_time).total_seconds() < EXCHANGE_RATE_CACHE_DURATION_SECONDS:
            rate = st.session_state[cache_key_rate]
            source_message = f"キャッシュされたレート (表示用, {base_currency}-{target_currency}, {last_updated_time.strftime('%Y-%m-%d %H:%M:%S UTC')}時点)"
            return rate, source_message
    try:
        fetched_rate = get_calc_exchange_rate(f"{base_currency}-{target_currency}", isDummy=False)
        if fetched_rate:
            st.session_state[cache_key_rate] = fetched_rate
            st.session_state[cache_key_time] = datetime.utcnow()
            rate = fetched_rate
            source_message = f"最新レート (表示用, {base_currency}-{target_currency}, Google Financeより)"
        else:
            raise ValueError("レート取得関数がNoneを返しました")
    except Exception as e:
        logger.error(f"表示用為替レート取得に失敗 ({base_currency}-{target_currency}): {e}。デフォルトレート ({DEFAULT_SGD_TO_JPY_RATE_DISPLAY}) を使用します。")
        if rate is None:
             rate = DEFAULT_SGD_TO_JPY_RATE_DISPLAY
             source_message = f"デフォルトレート (表示用, {base_currency}-{target_currency}, 取得失敗のため)"
        st.toast(f"{base_currency}-{target_currency}の表示用為替レート取得に失敗。デフォルト値を使用します。", icon="⚠️")
    return rate, source_message

# --- 最低仕入れ価格計算セクション (変更なし) ---
with st.expander("🧮 Shopee最低仕入れ価格 計算ツール (クリックで展開)"):
    st.markdown("Shopeeシンガポールでの販売価格と重量から、日本での最低仕入れ価格の目安を計算します。")
    display_rate_sgd_jpy_calc, display_rate_source_msg_calc = get_cached_exchange_rate_for_display()
    if display_rate_sgd_jpy_calc:
        st.info(f"参考為替レート: 1 SGD = {display_rate_sgd_jpy_calc:.2f} JPY ({display_rate_source_msg_calc})")
    else:
        st.warning("参考為替レートの表示に失敗しました。")
    with st.form(key="price_calculator_form"):
        st.write("計算する商品の情報を入力してください。")
        calc_col1, calc_col2 = st.columns(2)
        with calc_col1:
            selling_price_sgd_input = st.number_input(
                "Shopee販売価格 (SGD)", min_value=0.01, value=50.0, step=0.01, format="%.2f",
                help="Shopeeシンガポールでの商品の販売価格をSGDで入力してください。"
            )
        with calc_col2:
            weight_kg_input = st.number_input(
                "商品重量 (kg)", min_value=0.001, value=1.0, step=0.1, format="%.1f",
                help="商品の重量をキログラム(kg)で入力してください。例: 0.5 (500gの場合)"
            )
        calculate_button = st.form_submit_button(label="最低仕入れ価格を計算する")
    if calculate_button:
        if selling_price_sgd_input <= 0: st.error("販売価格は0より大きい値を入力してください。")
        elif weight_kg_input <= 0: st.error("商品重量は0より大きい値を入力してください。")
        else:
            with st.spinner("最低仕入れ価格を計算中です..."):
                try:
                    calculation_result = calculate_minimum_purchase_price(selling_price_sgd_input, weight_kg_input)
                    st.subheader("🧮 計算結果")
                    # (中略 - 表示部分は前回と同じ)
                    res_col1, res_col2 = st.columns(2)
                    with res_col1:
                        st.metric(label="🇸🇬 シンガポール販売価格", value=f"{calculation_result['selling_price_sgd']:.2f} SGD")
                        st.metric(label="⚖️ 商品重量", value=f"{calculation_result['weight_kg']:.1f} kg")
                        st.metric(label="💹 計算時為替レート", value=f"{calculation_result['exchange_rate']:.2f} JPY/SGD")
                        st.metric(label="✈️ SLS送料 (国際)", value=f"{calculation_result['sls_fee']:.0f} JPY")
                    with res_col2:
                        st.metric(label="🇯🇵 日本円換算 (販売価格)", value=f"{calculation_result['selling_price_jpy']:.0f} JPY")
                        st.metric(label="🚚 国内送料 (想定)", value=f"{calculation_result['domestic_shipping_fee']:.0f} JPY")
                        st.metric(label="💰 Shopee手数料", value=f"{calculation_result['shopee_fee']:.0f} JPY ({calculation_result['country_fee_rate']*100:.1f}%)")
                        st.metric(label="📈 想定利益", value=f"{calculation_result['profit']:.0f} JPY ({calculation_result['profit_margin']*100:.1f}%)")
                    st.markdown("---")
                    st.subheader("🎯 最低仕入れ価格の目安")
                    price_col1, price_col2 = st.columns(2)
                    with price_col1:
                        st.success(f"**最低仕入れ価格 (JPY): {calculation_result['minimum_purchase_price_jpy']:.0f} 円**")
                    with price_col2:
                        st.info(f"**最低仕入れ価格 (SGD): {calculation_result['minimum_purchase_price_sgd']:.2f} SGD**")
                    st.caption("この金額以下で商品を仕入れることができれば、設定した利益率が見込めます。")
                except ValueError as ve: st.error(f"計算エラー: {ve}")
                except NotImplementedError as nie: st.error(f"計算機能エラー: {nie}")
                except Exception as e: st.error(f"計算中に予期せぬエラーが発生しました: {e}")

# --- ファイルアップロードセクション (変更なし) ---
with st.expander("📤 商品一覧HTMLファイルをアップロードしてDBに登録/更新 (クリックで展開)"):
    # (内容は前回と同じなので省略)
    uploaded_html_files = st.file_uploader(
        "Shopeeの商品一覧HTMLファイルを選択してください。", type="html", accept_multiple_files=True,
        help="複数のHTMLファイルを一度にアップロードできます。", key="product_list_html_uploader"
    )
    if uploaded_html_files:
        st.info(f"{len(uploaded_html_files)}個の商品一覧HTMLファイルをAPIサーバーに送信します。")
        # (中略 - アップロード処理は前回と同じ)
        progress_bar_upload = st.progress(0)
        status_text_upload = st.empty()
        all_results = []
        for i, uploaded_file in enumerate(uploaded_html_files):
            file_name = uploaded_file.name
            status_text_upload.text(f"APIサーバーに送信中: {file_name} ({i+1}/{len(uploaded_html_files)})")
            try:
                response = requests.post(
                    FASTAPI_UPLOAD_PRODUCT_LIST_URL,
                    files=[('html_files', (file_name, uploaded_file.getvalue(), uploaded_file.type))]
                )
                response.raise_for_status()
                results_for_this_request = response.json()
                if isinstance(results_for_this_request, list) and results_for_this_request:
                    result = results_for_this_request[0]
                    all_results.append(result)
                    if result.get("status") == "success":
                        st.success(f"✅ ファイル '{file_name}' 処理成功: {result.get('message', 'データベースに保存/更新されました。')} (処理アイテム数: {result.get('items_processed', 0)})")
                    elif result.get("status") == "skipped":
                        st.warning(f"⚠️ ファイル '{file_name}' スキップ: {result.get('message', '処理されませんでした。')}")
                    else:
                        st.error(f"❌ ファイル '{file_name}' 処理失敗: {result.get('message', '不明なエラーが発生しました。')}")
                else:
                    st.error(f"❌ ファイル '{file_name}' のAPIからのレスポンス形式が不正です。")
                    all_results.append({"file_name": file_name, "status": "error", "message": "APIレスポンス形式不正"})
            except requests.exceptions.ConnectionError:
                st.error("🚨 商品リスト情報APIサーバーに接続できませんでした。") ; break
            except requests.exceptions.HTTPError as e:
                st.error(f"🚨 商品リスト情報APIサーバーからエラー ({e.response.status_code}): {e.response.text}")
            except Exception as e:
                st.error(f"🚨 ファイル '{file_name}' の処理中にエラー: {e}")
            progress_bar_upload.progress((i + 1) / len(uploaded_html_files))
        status_text_upload.text("ファイル送信処理が完了しました。")
        progress_bar_upload.empty()


# --- DBから商品リスト情報を検索・表示するセクション ---
st.header("🔍 データベース内の商品リスト情報を検索・表示・更新")

# 表示する可能性のある全カラムのリスト (ソーシング情報カラム追加)
ALL_PRODUCT_LIST_COLUMNS = [
    "id", "product_url", "product_name", "price", "currency", "image_url", 
    "location", "sold", "shop_type", "list_type", 
    "sourcing_status", "sourcing_notes", "status_updated_at", # ★追加！
    "created_at", "updated_at"
]
# デフォルトで表示するカラム (ソーシング情報も追加)
DEFAULT_PRODUCT_LIST_DISPLAY_COLUMNS = [
    "product_name", "price", "currency", "sold", "shop_type", "list_type", 
    "sourcing_status", "status_updated_at", # ★追加！
    "product_url"
]

# 検索フォームの外で為替レート情報を表示
if 'display_rate_sgd_jpy' not in globals() or 'display_rate_source_msg' not in globals():
    display_rate_sgd_jpy, display_rate_source_msg = get_cached_exchange_rate_for_display()
if display_rate_sgd_jpy:
    st.caption(f"参考為替レート (表示用): 1 SGD = {display_rate_sgd_jpy:.2f} JPY ({display_rate_source_msg})")


with st.form(key="product_list_search_form_with_sourcing"):
    st.subheader("絞り込み条件")
    # (中略 - 価格、販売数、ショップタイプ、リストタイプの入力は前回と同じ)
    c1, c2 = st.columns(2)
    with c1:
        st.write("価格範囲 (日本円で入力)")
        price_jpy_min = st.number_input("最小価格 (円)", min_value=0, value=None, placeholder="例: 5000", key="pl_price_jpy_min_s")
        price_jpy_max = st.number_input("最大価格 (円)", min_value=0, value=None, placeholder="例: 30000", key="pl_price_jpy_max_s")
    with c2:
        st.write("販売数範囲")
        min_sold = st.number_input("最小販売数", min_value=0, value=3, key="pl_min_sold_s")
        max_sold = st.number_input("最大販売数", min_value=0, value=100, key="pl_max_sold_s")
    
    c3, c4, c5 = st.columns(3) # ★ソーシングステータス用に列を追加
    with c3:
        shop_type_options = ["", "Standard", "Preferred", "Mall", "Official Store"]
        selected_shop_type = st.selectbox("ショップタイプ", options=shop_type_options, index=0, key="pl_shop_type_s")
    with c4:
        list_type_options = ["", "ショップ", "検索/カテゴリー", "汎用", "不明"]
        selected_list_type = st.selectbox("リストタイプ", options=list_type_options, index=0, key="pl_list_type_s")
    with c5:
        # ★ソーシングステータスでの絞り込みを追加！
        selected_sourcing_status = st.selectbox(
            "ソーシング状況", options=SOURCING_STATUS_OPTIONS, index=0, # SOURCING_STATUS_OPTIONS を使う
            help="特定のソーシング状況の商品に絞り込みます。", key="pl_sourcing_status_s"
        )
        
    st.write("登録日 (期間指定)")
    # (中略 - 登録日の入力は前回と同じ)
    col_date1, col_date2 = st.columns(2)
    with col_date1: start_date_created = st.date_input("開始日", value=None, key="pl_start_date_s")
    with col_date2: end_date_created = st.date_input("終了日", value=None, key="pl_end_date_s")

    st.subheader("表示オプション")
    # (中略 - 表示項目選択、オフセット、リミットの入力は前回と同じ)
    selected_columns_to_display = st.multiselect(
        "検索結果のテーブルに表示する項目:", options=ALL_PRODUCT_LIST_COLUMNS,
        default=DEFAULT_PRODUCT_LIST_DISPLAY_COLUMNS, key="pl_display_cols_s"
    )
    offset = st.number_input("表示開始位置 (オフセット)", min_value=0, value=0, step=20, key="pl_offset_s")
    limit = st.number_input("最大表示件数 (リミット)", min_value=1, max_value=10000, value=50, step=10, key="pl_limit_s")
    
    search_and_update_button = st.form_submit_button(label="この条件で検索・表示")

# セッションステートで検索結果を保持 (ページまたぎや更新UIのために)
if 'searched_product_list_df' not in st.session_state:
    st.session_state.searched_product_list_df = pd.DataFrame()

if search_and_update_button:
    search_params: Dict[str, Any] = {"offset": offset, "limit": limit}
    # (中略 - 価格、販売数などのパラメータ組み立ては前回と同じ)
    if display_rate_sgd_jpy:
        if price_jpy_min is not None: search_params["min_price_sgd"] = round(price_jpy_min / display_rate_sgd_jpy, 2)
        if price_jpy_max is not None: search_params["max_price_sgd"] = round(price_jpy_max / display_rate_sgd_jpy, 2)
    elif price_jpy_min is not None or price_jpy_max is not None:
        st.warning("為替レートが利用できないため、円での価格指定は無視されます。")
    if min_sold is not None: search_params["min_sold"] = min_sold
    if max_sold is not None: search_params["max_sold"] = max_sold
    if selected_shop_type: search_params["shop_type"] = selected_shop_type
    if selected_list_type: search_params["list_type"] = selected_list_type
    if selected_sourcing_status: search_params["sourcing_status"] = selected_sourcing_status # ★追加！
    if start_date_created: search_params["start_date_created"] = datetime.combine(start_date_created, datetime.min.time()).isoformat()
    if end_date_created: search_params["end_date_created"] = datetime.combine(end_date_created, datetime.max.time()).isoformat()
        
    st.markdown("---")
    st.subheader("現在の検索条件 (API送信値)")
    # (中略 - 検索条件表示は前回と同じ)
    active_search_filters = {k: v for k, v in search_params.items() if v is not None and k not in ["offset", "limit"]}
    if active_search_filters: st.json(active_search_filters)
    else: st.info("現在、絞り込み条件は指定されていません。")

    with st.spinner("商品リスト情報をデータベースから検索中です..."):
        try:
            response = requests.get(FASTAPI_BASIC_PRODUCTS_URL, params=search_params)
            response.raise_for_status()
            searched_data = response.json()
            
            if searched_data:
                st.session_state.searched_product_list_df = pd.DataFrame(searched_data) # 検索結果をセッションステートに保存
                # (以降の表示ロジックはセッションステートのデータを使うように変更するが、まずはここまで)
            else:
                st.session_state.searched_product_list_df = pd.DataFrame() # 空のDataFrameをセット
                st.info("指定された条件に一致する商品リスト情報は見つかりませんでした。")
        # (中略 - エラーハンドリングは前回と同じ)
        except requests.exceptions.ConnectionError:
            st.error("🚨 商品リスト情報APIサーバーに接続できませんでした。")
        except requests.exceptions.HTTPError as e:
            st.error(f"🚨 商品リスト情報APIサーバーからエラー ({e.response.status_code}): {e.response.text}")
        except Exception as e:
            st.error(f"🚨 商品リスト情報の検索中にエラー: {e}")

# --- 検索結果の表示とソーシング情報更新UI ---
if not st.session_state.searched_product_list_df.empty:
    df_to_display = st.session_state.searched_product_list_df
    st.subheader(f"検索結果: {len(df_to_display)} 件の商品が見つかりました")
    
    # 表示項目の選択 (フォームの外に出して、検索後にも変更できるようにする)
    # (ただし、これを動的にするには、再検索ボタンか、コールバックが必要になる。今回はシンプルに検索時の選択を優先)
    if selected_columns_to_display: # search_buttonが押された時の値を使う
        cols_to_show = [col for col in selected_columns_to_display if col in df_to_display.columns]
        if cols_to_show:
             st.dataframe(df_to_display[cols_to_show], use_container_width=True, hide_index=True)
        else:
             st.warning("選択された表示項目が検索結果に存在しません。全項目を表示します。")
             st.dataframe(df_to_display, use_container_width=True, hide_index=True)
    else: # submit_button が押されてない初回など
        cols_to_show_default = [col for col in DEFAULT_PRODUCT_LIST_DISPLAY_COLUMNS if col in df_to_display.columns]
        if cols_to_show_default:
            st.dataframe(df_to_display[cols_to_show_default], use_container_width=True, hide_index=True)
        else:
            st.dataframe(df_to_display, use_container_width=True, hide_index=True)


    st.subheader("商品画像プレビュー と ソーシング情報更新 (先頭最大10件)")
    # (画像プレビューとソーシング更新UIをここに組み込む)
    for index, row_series in df_to_display.head(10).iterrows(): # DataFrameの行をイテレート (Seriesとして取得)
        # row_series を辞書に変換
        row = row_series.to_dict()
        item_id = row.get("id")
        if not item_id: continue # IDがなければスキップ

        col_img, col_info, col_sourcing = st.columns([1, 3, 2]) # 画像、基本情報、ソーシング更新UI用

        with col_img:
            if row.get("image_url"):
                st.image(row["image_url"], width=100)
        
        with col_info:
            st.markdown(f"**{row.get('product_name', '商品名なし')}**")
            st.caption(f"価格: {row.get('price')} {row.get('currency')} | 販売数: {row.get('sold', 0)}")
            if row.get('product_url'):
                st.markdown(f"[Shopeeで見る]({row['product_url']})")
            st.caption(f"リストタイプ: {row.get('list_type', '不明')} | ショップタイプ: {row.get('shop_type', '不明')}")
            st.caption(f"DB登録日: {row.get('created_at')}")
            st.caption(f"情報最終更新日: {row.get('updated_at')}")


        with col_sourcing:
            # 各アイテムのソーシング情報を更新するためのフォーム
            # item_id ごとにユニークなキーを使う必要がある
            with st.form(key=f"sourcing_form_{item_id}"):
                current_status = row.get("sourcing_status") if row.get("sourcing_status") else SOURCING_STATUS_OPTIONS[0] # "" をデフォルトに
                # SOURCING_STATUS_OPTIONS に current_status がなければ、デフォルトのインデックスを使う
                try:
                    status_index = SOURCING_STATUS_OPTIONS.index(current_status)
                except ValueError:
                    status_index = 0 # 見つからなければ「指定なし」

                new_status = st.selectbox(
                    "ソーシング状況", SOURCING_STATUS_OPTIONS, 
                    index=status_index, 
                    key=f"status_{item_id}"
                )
                new_notes = st.text_area(
                    "作業メモ", value=row.get("sourcing_notes", ""), 
                    height=100,
                    key=f"notes_{item_id}"
                )
                sourcing_submit_button = st.form_submit_button("この商品の情報を更新")

                if sourcing_submit_button:
                    payload = {}
                    if new_status != row.get("sourcing_status"):
                        payload["sourcing_status"] = new_status if new_status else None # 空文字はNoneとして送信
                    if new_notes != row.get("sourcing_notes"):
                        payload["sourcing_notes"] = new_notes
                    
                    if payload: # 何か更新する情報がある場合のみAPIを叩く
                        update_url = FASTAPI_SOURCING_INFO_URL_TEMPLATE.format(item_id=item_id)
                        try:
                            response_update = requests.put(update_url, json=payload)
                            response_update.raise_for_status()
                            updated_item_data = response_update.json()
                            st.success(f"商品ID {item_id} のソーシング情報を更新しました！")
                            # ★★★ ここで検索結果のDataFrame (st.session_state.searched_product_list_df) を直接更新 ★★★
                            #     または、再度APIから全データをフェッチし直す（今回は前者で試す）
                            #     df の該当行を更新する
                            for idx, r in st.session_state.searched_product_list_df.iterrows():
                                if r['id'] == item_id:
                                    if "sourcing_status" in payload:
                                        st.session_state.searched_product_list_df.loc[idx, 'sourcing_status'] = payload["sourcing_status"]
                                    if "sourcing_notes" in payload:
                                        st.session_state.searched_product_list_df.loc[idx, 'sourcing_notes'] = payload["sourcing_notes"]
                                    st.session_state.searched_product_list_df.loc[idx, 'status_updated_at'] = updated_item_data.get('status_updated_at')
                                    st.session_state.searched_product_list_df.loc[idx, 'updated_at'] = updated_item_data.get('updated_at')
                                    break
                            st.rerun() # UIを再描画して更新を即時反映

                        except requests.exceptions.RequestException as e_req:
                            st.error(f"商品ID {item_id} のソーシング情報更新中にAPIエラー: {e_req}")
                        except Exception as e_gen:
                            st.error(f"商品ID {item_id} のソーシング情報更新中にエラー: {e_gen}")
                    else:
                        st.info(f"商品ID {item_id} のソーシング情報に変更はありませんでした。")
        st.markdown("---")


    # ダウンロードボタン (検索結果全体に対して)
    if not df_to_display.empty:
        col_dl1_pl, col_dl2_pl = st.columns(2)
        with col_dl1_pl:
            st.download_button("現在の検索結果をCSV形式でダウンロード", df_to_display.to_csv(index=False).encode('utf-8'), "shopee_searched_product_list_data.csv", "text/csv", key="download_searched_pl_csv_bottom", use_container_width=True)
        with col_dl2_pl:
            st.download_button("現在の検索結果をJSON形式でダウンロード", df_to_display.to_json(orient="records", indent=4).encode('utf-8'), "shopee_searched_product_list_data.json", "application/json", key="download_searched_pl_json_bottom", use_container_width=True)

elif search_and_update_button: # 検索ボタンは押されたが結果が空だった場合
    st.info("指定された条件に一致する商品リスト情報は見つかりませんでした。")
else:
    st.info("上記のフォームに条件を入力し、「この条件で検索・表示」ボタンを押すと、データベースから商品リスト情報が検索されます。")
