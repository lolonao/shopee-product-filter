# 計画書: `shopee_price_pilot` のコード統合とリファクタリング

## 目的

`shopee-product-prospector` プロジェクトに、`shopee_price_pilot` の価格計算機能をライブラリとしてではなく、ソースコードを直接コピー（ベンダー化）して統合する。これにより、外部依存を減らし、プロジェクトの自己完結性を高める。

---

### フェーズ1: `shopee_price_pilot` のソースコードの移動 (完了)

- [x] **1-1.** 新しいディレクトリ `src/shopee_price_pilot` を作成する。
- [x] **1-2.** `src/shopee_price_pilot/__init__.py` という空のファイルを作成し、このディレクトリをPythonパッケージとして認識させる。
- [x] **1-3.** `TMP/shopee_price_pilot-develop/src/shopee_price_pilot/calculator.py` を `src/shopee_price_pilot/` にコピーする。
- [x] **1-4.** `TMP/shopee_price_pilot-develop/src/shopee_price_pilot/models.py` を `src/shopee_price_pilot/` にコピーする。
- [x] **1-5.** `TMP/shopee_price_pilot-develop/src/shopee_price_pilot/exchange.py` を `src/shopee_price_pilot/` にコピーする。
- [x] **1-6.** `shopee_price_pilot` が必要とする設定ファイルとデータファイルを、プロジェクトの `data/` ディレクトリにコピーする。
    - [x] `TMP/shopee_price_pilot-develop/data/config.json` -> `data/price_pilot_config.json`
    - [x] `TMP/shopee_price_pilot-develop/data/shipping_rates_sg.csv` -> `data/shipping_rates_sg.csv`
    - [x] `TMP/shopee_price_pilot-develop/data/shipping_rates_ph.csv` -> `data/shipping_rates_ph.csv`

### フェーズ2: プロジェクト構成の修正 (srcレイアウト対応) (完了)

- [x] **2-1.** `pyproject.toml` を編集し、`[tool.setuptools.packages.find]` を追加して、`src` ディレクトリがソースコードのルートであることを明示する。
- [x] **2-2.** `uv pip install -e .` を実行し、新しいプロジェクト構成をシステムに認識させる。

### フェーズ3: アプリケーションの修正 (完了)

- [x] **3-1.** `shopee_price_pilot` のデータローダー (`data_loader.py`) を、このプロジェクトのディレクトリ構造で動作するように修正し、`src/shopee_price_pilot/` にコピーする。
- [x] **3-2.** 不要になった `src/shopee_product_filter/app/calculator.py` を削除する。
- [x] **3-3.** Streamlitアプリ (`app.py`) と FastAPIサーバー (`product_list_api.py`) 内のインポート文を、`src` レイアウトで動作するように修正する。
- [x] **3-3-1 (新規).** `uv run` を使って `uvicorn` と `streamlit` を実行することで、`ModuleNotFoundError` を解決し、アプリケーションを正常に起動できるようにした。
- [ ] **3-4.** 計算機に入力値のバリデーションを追加し、範囲外の場合はUIに警告を表示する。

### フェーズ4: 最終クリーンアップと検証 (進行中)

- [ ] **4-1.** `examples` ディレクトリ全体を削除する。
- [ ] **4-2.** `TMP` ディレクトリ全体を削除する。
- [x] **4-3.** アプリケーションを起動し、価格計算機能が正常に動作することを検証する。

---

この計画書に沿って作業を進めるわね。
