### **作業計画書: `shopee-product-filter` への `shopee_price_pilot` 統合**

#### **1. 目的**
`shopee-product-filter` のStreamlitアプリケーション（`product_list_streamlit_app_type1.py`）における「最低仕入れ価格計算」機能を、より高機能な `shopee_price_pilot` ライブラリの計算ロジックに置き換えることで、計算の精度と柔軟性を向上させる。

#### **2. 統合の範囲**
*   `shopee-product-filter` プロジェクトへの `shopee_price_pilot` の依存関係追加。
*   `shopee-product-filter/src/shopee_product_filter/app/product_list_streamlit_app_type1.py` の改修。
*   「最低仕入れ価格計算」機能における `shopee_price_pilot.calculator.PriceCalculator` の利用。
*   容積重量に関するUI入力と結果表示の追加。

#### **3. 作業フェーズとTODOリスト**

##### **フェーズ0: 準備と環境構築**
*   **目的:** 開発環境を整え、作業ブランチを作成する。
*   **TODO:**
    *   [ ] `shopee-product-filter` リポジトリをローカルにクローンする。
    *   [ ] 新しいフィーチャーブランチを作成する（例: `feature/integrate-price-pilot`）。

##### **フェーズ1: 依存関係の追加**
*   **目的:** `shopee-product-filter` プロジェクトに `shopee_price_pilot` を依存関係として追加し、インストールする。
*   **TODO:**
    *   [ ] `shopee-product-filter` の `pyproject.toml` を開き、`[project]` セクションの `dependencies` に `shopee-price-pilot` を追加する。
        *   *注: `shopee-price-pilot` はローカルパスまたはパッケージレジストリからインストールできるように設定する必要がある。今回はローカルパスでの開発を想定。*
    *   [ ] `shopee-product-filter` プロジェクトのルートディレクトリで `uv pip install -e .` を実行し、新しい依存関係をインストールする。

**フェーズ2: Streamlitアプリの改修**
- [x]  に  の必要モジュールをインポートする。
- [x]  等を初期化する処理を追加する。
- [x] UIに商品サイズ（縦・横・高さ）の入力欄を追加する。
- [x] 既存の計算ロジックを  の呼び出しに置き換える。
- [x] 計算結果（容積重量、実効重量など）をUIに表示するよう更新する。

##### **フェーズ3: テストと検証**
*   **目的:** 統合された機能が正しく動作することを確認する。
*   **TODO:**
    *   [ ] `shopee-product-filter` のStreamlitアプリケーションを起動する。
    *   [ ] 「最低仕入れ価格計算」機能で、様々な入力値（特に商品サイズ）を試す。
    *   [ ] 計算結果（最低仕入れ価格、SLS送料、容積重量、実効重量など）が期待通りに表示されることを確認する。
    *   [ ] 既存の `shopee-product-filter` のテストがあれば実行し、回帰がないことを確認する。

##### **フェーズ4: コードレビューとクリーンアップ**
*   **目的:** コードの品質を確保し、不要なコードを削除する。
*   **TODO:**
    *   [x] コードのフォーマットとリンティングを実行する。
    *   [x] 不要になった既存の計算ロジックやインポートを削除する。
    *   [ ] コメントやドキュメンテーションを適切に更新する。

#### **4. 為替レート機能の置き換えに関する議論**

Naoさん、為替レート機能についてのご提案、ありがとうございます。
`shopee_price_pilot` の為替レートモジュールに置き換えるという方針、ジーナも賛成です。これにより、為替レート取得ロジックが一元化され、保守性が向上すると考えられます。

**置き換えのメリット:**
*   **一貫性:** 為替レートの取得とキャッシュのロジックが `shopee_price_pilot` に集約されるため、両プロジェクトで同じ信頼性の高いレートが利用できる。
*   **保守性:** 為替レートAPIの変更やエラーハンドリングの改善が必要になった場合、`shopee_price_pilot` の一箇所を修正するだけで済む。
*   **機能強化:** `shopee_price_pilot` の為替レートモジュールが持つキャッシュ機能などを活用できる。

**考慮すべき点:**
*   **APIキー/設定:** `shopee_price_pilot` の為替レートモジュールが外部APIを使用する場合、そのAPIキーや設定を `shopee-product-filter` 側でどのように管理・提供するか。
*   **既存機能との連携:** `shopee-product-filter` の既存の為替レート取得ロジック（特に `product_list_streamlit_app_type2.py` での利用）との整合性をどう取るか。
*   **エラーハンドリング:** 為替レート取得に失敗した場合のユーザーへの通知やフォールバック戦略。

この置き換えは、今回の「最低仕入れ価格計算」の統合が完了し、安定した後に、**次のフェーズ**として取り組むのが良いでしょう。

**次のフェーズのTODO（案）:**
*   [ ] `shopee-product-filter` の既存の為替レート取得ロジックを特定する。
*   [ ] `shopee_price_pilot.exchange.ExchangeRateProvider` を使用するように置き換える。
*   [ ] 為替レート取得に関するエラーハンドリングを強化する。
*   [ ] 置き換え後の動作を徹底的にテストする。

**【重要】次回のセッションは、`shopee-product-filter` リポジトリに移動してから再開します。**