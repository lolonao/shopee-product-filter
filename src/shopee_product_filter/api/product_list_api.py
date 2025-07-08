import os
import sys
import logging
from typing import List, Optional, Dict, Any, Annotated
from datetime import datetime, timezone
import tempfile
from contextlib import asynccontextmanager

# FastAPI のインポート
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import HTMLResponse
# SQLModel と SQLAlchemy の select
from sqlmodel import Field, Session, SQLModel, create_engine, select
from sqlalchemy.sql.expression import and_
from pydantic import BaseModel

# parse_product_list.py を同じディレクトリからインポート
from ..core.parse_product_list import parse_shopee_shop_products_from_file_final

# BeautifulSoup をインポート
from bs4 import BeautifulSoup

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

# --- 商品リスト情報専用のDB設定 ---
DB_FILE_PRODUCT_LIST = "shopee_product_list_data.db"
DATABASE_URL_PRODUCT_LIST = f"sqlite:///{DB_FILE_PRODUCT_LIST}"

logger.info(f"商品リスト情報APIは、データベースファイル '{DB_FILE_PRODUCT_LIST}' を使用します。")

engine_product_list = create_engine(DATABASE_URL_PRODUCT_LIST, echo=False)

# --- SQLModelの商品リスト情報モデル定義 (変更なし) ---
class ProductBasicItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    product_url: str = Field(unique=True, index=True, max_length=2048)
    product_name: Optional[str] = Field(default=None, max_length=512)
    price: Optional[float] = None
    currency: Optional[str] = Field(default=None, max_length=10)
    image_url: Optional[str] = Field(default=None, max_length=2048)
    location: Optional[str] = Field(default=None, max_length=255)
    sold: Optional[int] = Field(default=0)
    shop_type: Optional[str] = Field(default=None, max_length=50)
    list_type: Optional[str] = Field(default=None, max_length=50)
    sourcing_status: Optional[str] = Field(default=None, index=True, max_length=50)
    sourcing_notes: Optional[str] = Field(default=None)
    status_updated_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

# --- ソーシング情報更新用のリクエストボディモデル (変更なし) ---
class SourcingInfoUpdate(BaseModel):
    sourcing_status: Optional[str] = None
    sourcing_notes: Optional[str] = None

# --- FastAPIのライフサイクルイベント管理 (変更なし) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"商品リスト情報API起動シーケンス開始 (lifespan)。データベースファイル: '{DB_FILE_PRODUCT_LIST}'")
    try:
        SQLModel.metadata.create_all(engine_product_list)
        actual_table_name = "productbasicitem"
        logger.info(f"商品リスト情報データベース '{DB_FILE_PRODUCT_LIST}' のテーブル '{actual_table_name}' を確認/作成しました。")
    except Exception as e:
        logger.critical(f"商品リスト情報データベース '{DB_FILE_PRODUCT_LIST}' の起動エラー (lifespan): {e}", exc_info=True)
    yield
    logger.info("商品リスト情報APIシャットダウン完了 (lifespan)。")

# FastAPIのインスタンスを生成
product_list_app = FastAPI(
    title="🛍️ Shopee 商品リスト情報 API (ソーシング機能付き)",
    description="商品一覧HTMLから抽出した基本情報を管理・検索し、ソーシング状況も記録できるAPIだぜ！",
    version="1.1.7", # 引数の順番 修正バージョン！
    lifespan=lifespan
)

# --- DBセッションの定義 (変更なし) ---
def get_product_list_session():
    with Session(engine_product_list) as session:
        yield session
ProductListSession = Annotated[Session, Depends(get_product_list_session)]


# --- API エンドポイント ---
@product_list_app.get("/", response_class=HTMLResponse, summary="商品リストAPIのトップページ")
async def read_product_list_root():
    # (内容は変更なし)
    return f"""
    <html><head><title>Shopee 商品リスト情報 API (ソーシング機能付き)</title></head>
    <body><h1>🛍️ Shopee 商品リスト情報 API へようこそ！</h1>
    <p>このAPIは商品リストの基本情報とソーシング状況を管理します。Streamlitアプリからどうぞ。</p>
    <ul><li><a href="/docs">APIドキュメント (Swagger UI)</a></li><li><a href="/redoc">APIドキュメント (ReDoc)</a></li><li><a href="/basic-products/">DB内商品リスト情報取得</a></li></ul>
    </body></html>"""

@product_list_app.get("/basic-products/", response_model=List[ProductBasicItem], summary="商品リスト情報を取得・検索")
def get_basic_products_with_filters(
    # ★★★ session をデフォルト値を持つ引数の前に持ってくる ★★★
    session: ProductListSession,
    offset: int = 0,
    limit: int = Query(default=100, le=200),
    min_price_sgd: Optional[float] = Query(default=None),
    max_price_sgd: Optional[float] = Query(default=None),
    min_sold: Optional[int] = Query(default=None),
    max_sold: Optional[int] = Query(default=None),
    shop_type: Optional[str] = Query(default=None),
    list_type: Optional[str] = Query(default=None),
    sourcing_status: Optional[str] = Query(default=None),
    start_date_created: Optional[datetime] = Query(default=None),
    end_date_created: Optional[datetime] = Query(default=None),
):
    conditions = []
    if min_price_sgd is not None: conditions.append(ProductBasicItem.price >= min_price_sgd)  # type: ignore
    if max_price_sgd is not None: conditions.append(ProductBasicItem.price <= max_price_sgd)  # type: ignore
    if min_sold is not None: conditions.append(ProductBasicItem.sold >= min_sold)      # type: ignore
    if max_sold is not None: conditions.append(ProductBasicItem.sold <= max_sold)      # type: ignore
    if shop_type: conditions.append(ProductBasicItem.shop_type == shop_type)  # type: ignore
    if list_type: conditions.append(ProductBasicItem.list_type == list_type)  # type: ignore
    if sourcing_status: conditions.append(ProductBasicItem.sourcing_status == sourcing_status) # type: ignore
    if start_date_created: conditions.append(ProductBasicItem.created_at >= start_date_created) # type: ignore
    if end_date_created: conditions.append(ProductBasicItem.created_at <= end_date_created) # type: ignore
    
    statement = select(ProductBasicItem)
    if conditions:
        statement = statement.where(and_(*conditions))
        
    statement = statement.offset(offset).limit(limit).order_by(ProductBasicItem.id)
    products = session.exec(statement).all()
    return products if products else []


@product_list_app.get("/basic-products/{item_id}", response_model=ProductBasicItem, summary="特定の商品リスト情報をIDで取得")
def get_basic_product_by_id(
    # ★★★ session をデフォルト値を持つ引数の前に持ってくる (この関数は item_id が必須なので元々OKだった) ★★★
    item_id: int, 
    session: ProductListSession
):
    product = session.get(ProductBasicItem, item_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品リストアイテムが見つかりません")
    return product

@product_list_app.put("/basic-products/{item_id}/sourcing-info", response_model=ProductBasicItem, summary="特定商品のソーシング情報を更新")
def update_sourcing_info(
    # ★★★ session をデフォルト値を持つ引数の前に持ってくる (item_id と sourcing_info が必須なので元々OKだった) ★★★
    item_id: int,
    sourcing_info: SourcingInfoUpdate,
    session: ProductListSession
):
    db_item = session.get(ProductBasicItem, item_id)
    if not db_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品リストアイテムが見つかりません")
    update_data = sourcing_info.model_dump(exclude_unset=True)
    changed = False
    for field_name, value in update_data.items():
        if hasattr(db_item, field_name) and getattr(db_item, field_name) != value:
            setattr(db_item, field_name, value)
            changed = True
    if changed:
        current_time = datetime.now(timezone.utc)
        db_item.status_updated_at = current_time
        db_item.updated_at = current_time
        session.add(db_item)
        session.commit()
        session.refresh(db_item)
        logger.info(f"商品ID {item_id} のソーシング情報を更新しました。")
    else:
        logger.info(f"商品ID {item_id} のソーシング情報に変更はありませんでした。")
    return db_item

@product_list_app.post("/upload-product-list-html/", summary="商品リストHTMLをアップロードしてDBに保存/更新")
async def upload_product_list_html_and_save(
    # ★★★ session をデフォルト値を持つ引数の前に持ってくる ★★★
    session: ProductListSession, 
    html_files: List[UploadFile] = File(...)
):
    # (以降のロジックは変更なし)
    processed_results = []
    for html_file in html_files:
        file_name = html_file.filename
        logger.info(f"商品リストHTMLファイル処理開始: {file_name}")
        temp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w+b") as tmp:
                content = await html_file.read()
                tmp.write(content)
                temp_file_path = tmp.name
            
            parsed_items: Optional[List[Dict[str, Any]]] = parse_shopee_shop_products_from_file_final(temp_file_path)

            if parsed_items is None:
                logger.warning(f"ファイル '{file_name}' から商品リストのコンテナが見つかりませんでした。スキップします。")
                processed_results.append({"file_name": file_name, "status": "skipped", "message": "商品リストのコンテナが見つかりませんでした。"})
                continue
            if not parsed_items:
                logger.info(f"ファイル '{file_name}' から抽出された商品アイテムはありませんでした。")
                processed_results.append({"file_name": file_name, "status": "success", "message": "抽出アイテムなし", "items_processed": 0})
                continue

            items_processed_count = 0
            soup_for_list_type = BeautifulSoup(content.decode('utf-8', errors='ignore'), 'lxml')
            detected_list_type = "不明"
            if soup_for_list_type.select('div.shop-search-result-view > div.row > div.shop-search-result-view__item'):
                detected_list_type = "ショップ"
            elif soup_for_list_type.select('li.col-xs-2-4.shopee-search-item-result__item'):
                detected_list_type = "検索/カテゴリー"
            elif soup_for_list_type.select('li[data-sqe="item"]'):
                detected_list_type = "汎用"
            logger.info(f"ファイル '{file_name}' の検出リストタイプ: {detected_list_type}")

            for item_data in parsed_items:
                product_url = item_data.get("product_url")
                if not product_url:
                    logger.warning(f"アイテムにproduct_urlがありません。スキップします。データ: {item_data}")
                    continue
                
                existing_item = session.exec(
                    select(ProductBasicItem).where(ProductBasicItem.product_url == product_url)
                ).first()
                current_time = datetime.now(timezone.utc)
                valid_model_keys = ProductBasicItem.model_fields.keys()

                if existing_item:
                    logger.info(f"商品URL '{product_url}' は既存のため、更新します。 (ファイル: {file_name})")
                    update_data = { k: v for k, v in item_data.items() if k in valid_model_keys and k not in ["created_at", "id", "sourcing_status", "sourcing_notes", "status_updated_at"]}
                    for key, value in update_data.items():
                        setattr(existing_item, key, value)
                    existing_item.list_type = detected_list_type
                    existing_item.updated_at = current_time
                    session.add(existing_item)
                else:
                    logger.info(f"商品URL '{product_url}' は新規のため、追加します。 (ファイル: {file_name})")
                    new_item_data_with_list_type = {**item_data, "list_type": detected_list_type}
                    filtered_new_item_data = { k: v for k, v in new_item_data_with_list_type.items() if k in valid_model_keys and k != "id"}
                    new_item = ProductBasicItem(**filtered_new_item_data)
                    session.add(new_item)
                items_processed_count += 1
            
            session.commit()
            processed_results.append({"file_name": file_name, "status": "success", "message": f"{items_processed_count} アイテム処理完了", "items_processed": items_processed_count})
            logger.info(f"ファイル '{file_name}' のDB保存/更新が完了しました。処理アイテム数: {items_processed_count}")

        except HTTPException:
            session.rollback()
            processed_results.append({"file_name": file_name, "status": "error", "message": "処理中にHTTPエラーが発生しました。"})
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"商品リストHTML '{file_name}' の処理中に予期せぬエラーが発生しました: {e}", exc_info=True)
            processed_results.append({"file_name": file_name, "status": "error", "message": f"予期せぬサーバーエラー: {e}"})
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try: os.remove(temp_file_path)
                except Exception as e_remove: logger.error(f"一時ファイルの削除に失敗: {temp_file_path}, エラー: {e_remove}")
                    
    return processed_results

