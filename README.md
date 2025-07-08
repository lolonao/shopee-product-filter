# 🛍️ Shopee 商品リスト・ソーシング管理システム

## 概要

このプロジェクトは、Shopeeの商品検索結果HTMLから商品情報を抽出し、データベースで管理、APIを通じて情報を提供し、Streamlitアプリケーションで視覚的に操作・分析するためのシステムです。商品の基本情報管理、ソーシング状況の記録、そして日本円での最低仕入れ価格計算機能を提供します。

## 機能

-   **HTMLからの商品情報抽出**: Shopeeの商品一覧HTMLファイル（ショップ、検索結果、カテゴリーページなど）から、商品名、価格、販売数、画像URL、ショップタイプ、リストタイプなどの基本情報を自動で抽出します。
-   **データベース管理**: 抽出した商品情報をSQLiteデータベースに保存し、重複を避けつつ最新の情報に更新します。
-   **RESTful API**: FastAPIを使用して、データベースに保存された商品情報へのアクセス、検索、ソーシング状況の更新を行うためのAPIエンドポイントを提供します。
-   **Streamlitユーザーインターフェース**: 直感的で使いやすいWeb UIを通じて、以下の操作が可能です。
    -   商品一覧HTMLファイルのアップロードとデータベースへの登録/更新。
    -   データベース内の商品情報を様々な条件（価格帯、販売数、ショップタイプ、リストタイプ、登録日など）で検索・絞り込み。
    -   検索結果の表示、CSV/JSON形式でのダウンロード。
    -   個々の商品の画像プレビューと詳細情報の確認。
    -   商品のソーシング状況（未着手、調査中、仕入先発見など）とメモの記録・更新。
    -   Shopeeシンガポールでの販売価格と重量から、日本での最低仕入れ価格を計算するツール。
-   **為替レートの自動取得とキャッシュ**: 為替レートを自動で取得し、Streamlitアプリ内でキャッシュすることで、計算の精度と効率を向上させます。

## プロジェクト構造

```
.
├── data/
│   └── shopee_product_list_data.db  # 商品情報データベース
├── docs/
│   └── 起動方法.md                  # 起動方法と開発セットアップのドキュメント
├── src/
│   ├── __init__.py
│   └── shopee_product_filter/       # メインアプリケーションパッケージ
│       ├── __init__.py
│       ├── api/                     # FastAPIアプリケーション関連
│       │   └── product_list_api.py  # FastAPIサーバーのメインファイル
│       ├── app/                     # Streamlitアプリケーション関連
│       │   ├── product_list_streamlit_app_type1.py # Streamlit UI (タイプ1)
│       │   └── product_list_streamlit_app_type2.py # Streamlit UI (タイプ2)
│       ├── core/                    # コアロジック（パーサー、計算機など）
│       │   ├── calc_buy_price.py
│       │   ├── calculator.py        # 価格計算ロジック
│       │   └── parse_product_list.py # HTMLパーサー
│       └── experiments/             # 実験的なスクリプトや一時的なコード
│           └── parse_product_list/
│               ├── parse_category_products.py
│               ├── parse_search_products.py
│               └── parse_shop_products.py
├── .gitignore
├── pyproject.toml                   # プロジェクト設定と依存関係
├── README.md                        # このファイル
└── uv.lock                          # uvによる依存関係ロックファイル
```

## セットアップ

### 1. 開発環境のセットアップ (初回のみ)

プロジェクトのルートディレクトリで、以下のコマンドを実行して、プロジェクトを編集可能な状態でインストールします。これにより、Pythonがプロジェクト内のモジュールを正しく見つけられるようになり、`PYTHONPATH=.` をコマンドの先頭につける必要がなくなります。また、コードを変更するたびに再インストールする必要はありません。

```bash
uv pip install -e .
```

### 2. データベースファイルの準備

SQLiteデータベースファイル `shopee_product_list_data.db` は、FastAPIサーバーが初回起動時に自動的に作成します。手動で準備する必要はありません。

## 使い方

### 1. FastAPIサーバーの起動

プロジェクトのルートディレクトリで、以下のコマンドを実行してFastAPIサーバーを起動します。

```bash
uv run uvicorn src.shopee_product_filter.api.product_list_api:product_list_app --reload --port 8002
```

サーバーが起動したら、ブラウザで [http://127.0.0.1:8002/docs](http://127.0.0.1:8002/docs) にアクセスすると、APIドキュメント（Swagger UI）を確認できます。

### 2. Streamlitアプリケーションの起動

FastAPIサーバーが起動していることを確認した後、別のターミナルで以下のコマンドを実行してStreamlitアプリケーションを起動します。

```bash
uv run streamlit run src/shopee_product_filter/app/product_list_streamlit_app_type1.py
```

アプリケーションが起動したら、ブラウザで表示されるURL（通常は [http://localhost:8501](http://localhost:8501)）にアクセスしてください。

## 使用技術

-   **Python**: 3.11+
-   **FastAPI**: 高性能なWeb APIフレームワーク
-   **Streamlit**: PythonでWebアプリを簡単に作成するためのフレームワーク
-   **SQLModel**: SQLデータベースとPythonオブジェクトを扱うためのライブラリ (SQLAlchemyとPydanticをベース)
-   **BeautifulSoup**: HTML/XML解析ライブラリ
-   **requests**: HTTPリクエストライブラリ
-   **uv**: 高速なPythonパッケージインストーラー兼パッケージマネージャー

## ライセンス

[ここにライセンス情報を記述します。例: MIT License]