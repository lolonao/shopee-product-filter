# TODO: DBカラム最適化とアプリ修正

## 目的

*   `ProductBasicItem` モデルから不要なフィールド (`location`, `list_type`, `status_updated_at`) を削除する。
*   残りのフィールドの並び順をNaoさんの指定通りに変更する。
*   変更に合わせてFastAPIとStreamlitアプリのコードを修正する。
*   新しいスキーマでデータベースを再作成する。

## 作業手順

### 1. `src/shopee_product_filter/api/product_list_api.py` の修正

-   [x] `ProductBasicItem` モデルの定義を以下のように変更する。
    ```python
    class ProductBasicItem(SQLModel, table=True):
        id: Optional[int] = Field(default=None, primary_key=True, index=True)
        sold: Optional[int] = Field(default=0)
        price: Optional[float] = None
        currency: Optional[str] = Field(default=None, max_length=10)
        product_name: Optional[str] = Field(default=None, max_length=512)
        shop_type: Optional[str] = Field(default=None, max_length=50)
        product_url: str = Field(unique=True, index=True, max_length=2048)
        image_url: Optional[str] = Field(default=None, max_length=2048)
        sourcing_status: Optional[str] = Field(default=None, index=True, max_length=50)
        sourcing_notes: Optional[str] = Field(default=None)
        created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
        updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    ```
-   [x] `upload_product_list_html_and_save` 関数内で、削除する `list_type` に関連する検出ロジックと、`new_item_data_with_list_type` への `list_type` の割り当てを削除する。

### 2. データベースファイルの削除

-   [x] 既存のデータベースファイル `data/shopee_product_list_data.db` を削除する。
    ```bash
    rm data/shopee_product_list_data.db
    ```
    *これにより、FastAPIサーバー起動時に新しいスキーマでデータベースが自動的に再作成されます。*

### 3. `src/shopee_product_filter/app/product_list_streamlit_app_type1.py` の修正

-   [x] `ALL_PRODUCT_LIST_COLUMNS` から `location`、`list_type`、`status_updated_at` を削除する。
-   [x] `DEFAULT_PRODUCT_LIST_DISPLAY_COLUMNS` から `list_type`、`status_updated_at` を削除する。
-   [x] 検索フォーム内の `location` と `list_type` に関連するUI要素（`st.selectbox` など）と、それらの検索パラメータを組み立てるロジックを削除する。
-   [x] 検索結果表示部分で `location` と `list_type` を参照している箇所を削除する。

### 4. `src/shopee_product_filter/app/product_list_streamlit_app_type2.py` の確認と修正

-   [x] `product_list_streamlit_app_type2.py` も同様に、`location`、`list_type`、`status_updated_at` の参照がないか確認し、あれば修正する。
-   [x] アップロード処理後のレスポンス処理を修正し、`AttributeError` を解消する。

### 5. 動作確認

-   [x] **FastAPIサーバーの起動**:
    `uv run uvicorn src.shopee_product_filter.api.product_list_api:product_list_app --reload --port 8002`
    *新しいスキーマで `shopee_product_list_data.db` が再作成されることを確認する。*
-   [x] **Streamlitアプリの起動**:
    `uv run streamlit run src/shopee_product_filter/app/product_list_streamlit_app_type1.py`
    *エラーなく動作すること、およびUIから削除されたフィールドが正しく反映されていることを確認する。*
-   [x] HTMLファイルをアップロードして、新しいスキーマでデータが保存されることを確認する。
-   [x] 検索機能が正しく動作することを確認する。

## 今後のタスクとTODO管理について

この `TODO.md` ファイルは、プロジェクトの現在のタスクと進捗状況を明確にするための重要なツールです。誤解を防ぎ、Naoさんとジーナの間で常に共通の認識を持つために、以下の点を遵守します。

-   **新しいタスクの追加**: 新しい機能開発やバグ修正のIssueが作成された際、必要に応じてこのファイルにタスクを追加します。
-   **進捗状況の更新**: タスクの開始、進行中、完了の各段階で、このファイルの該当項目を更新します。
-   **定期的な確認**: Naoさんとジーナは、作業を開始する前や、重要な決定を行う前に、このファイルを定期的に確認します。
-   **完了タスクのアーカイブ**: 完了した主要なタスクは、このファイルの該当項目をチェックマークでマークし、必要に応じて履歴として残します。

---

## ドキュメント整理

-   [x] `ISSUE_17_DEBUG_NOTES.md` を `docs/archive` に移動し、アーカイブする.
-   [x] `開発手順.md` の内容を確認し、必要であれば更新する.
-   [x] `アプリ仕様書.md` や `起動方法.md` の内容を確認し、必要であれば更新する.

---

## ISSUE #14: Streamlitアプリのページネーション関連UI/変数名の改善

-   [x] `product_list_streamlit_app_type1.py` のUIラベルと変数名を変更。
-   [x] `product_list_streamlit_app_type2.py` のUIラベルと変数名を変更。
-   [x] 動作確認済み。

---

## ISSUE #16: ソーシング情報更新時のAPIエラー (status_updated_at) の修正

-   [x] `src/shopee_product_filter/api/product_list_api.py` の `update_sourcing_info` 関数から不要な `status_updated_at` の設定を削除。
-   [x] 動作確認済み。

---

## ISSUE #17: Streamlitアプリのソーシング状況ドロップダウンの初期値を「未着手」にし、検索条件への自動追加を抑制

-   [x] `src/shopee_product_filter/app/product_list_streamlit_app_type1.py` のUI上の初期値を「未着手」に設定。
-   [x] `src/shopee_product_filter/app/product_list_streamlit_app_type1.py` の検索条件への自動追加を抑制。
-   [x] 動作確認済み.

---

## ISSUE #26: shopee_price_pilot統合による最低仕入れ価格計算機能の強化

- [x] Streamlitアプリ (`product_list_streamlit_app_type1.py`) に `shopee_price_pilot` の計算ロジックを統合。
- [x] `DummyExchangeRateProvider` の初期化エラーを修正。
- [x] 不要になった古い計算ロジックとインポートを削除。
- [x] コードのフォーマットとリンティングを実施。
- [ ] Streamlitアプリの手動テストと検証（Naoさんによる）。
- [ ] コメントやドキュメンテーションの更新（このタスクで実施）。
