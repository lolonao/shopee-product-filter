### 3つのプロジェクト統合案

#### **1. `shopee-product-filter` を中心とした統合**

`shopee-product-filter` が、Shopeeからのデータ取得、フィルタリング、そして想定仕入れ価格の算出を行う中心的なハブとなります。

#### **2. `shopee_price_pilot` の統合 (進行中)**

*   これは現在計画中の内容であり、`shopee-product-filter` の「最低仕入れ価格計算UI」に `shopee_price_pilot` の計算ロジックを組み込みます。これにより、容積重量を考慮したより正確な価格計算が可能になります。

#### **3. `product-title-aligner` の統合**

これが、Naoさんの「機能1: 英語の商品タイトルから、適切な日本の商品タイトル名への変換/想定」を実現する核となります。

*   **統合方法の検討:**
    *   **API連携:** `product-title-aligner` を独立したサービス（FastAPIなど）としてデプロイし、`shopee-product-filter` からそのAPIを呼び出す。これにより、モジュール間の疎結合を保ちつつ、機能を利用できます。
    *   **ライブラリとして組み込み:** `product-title-aligner` を `shopee-product-filter` の依存関係として追加し、直接モジュールをインポートして利用する。開発はシンプルになりますが、依存関係が密になります。

*   **具体的な連携フロー (案):**
    1.  `shopee-product-filter` でShopeeの商品情報を取得し、フィルタリングする。
    2.  フィルタリングされた商品の英語タイトルを `product-title-aligner` に渡し、日本語の商品タイトル候補を取得する。
    3.  取得した日本語の商品タイトル候補を元に、`shopee-product-filter` 内でAmazon Japanへの検索（`amazon_finder` の機能を利用）を実行する。

#### **4. `amazon_finder` の統合**

これが、Naoさんの「機能2: 想定された商品名を元にした日本国内ECサイトでの検索とリストアップ」を実現する核となります。

*   **統合方法の検討:**
    *   `amazon_finder` のAmazon検索・スクレイピング・類似度分析のロジックを、`shopee-product-filter` の内部モジュールとして組み込む。
    *   `amazon_finder` も独立したサービスとしてデプロイし、API連携する。

*   **具体的な連携フロー (案):**
    1.  `shopee-product-filter` が `product-title-aligner` から得た日本語の商品タイトル候補を受け取る。
    2.  これらの候補を使って、`amazon_finder` の検索ロジックを呼び出し、Amazon Japanで商品を検索し、結果をスクレイピングする。
    3.  `amazon_finder` の類似度分析機能を使って、Shopeeの商品とAmazonの候補商品の類似度を評価する。
    4.  最終的な結果（Shopeeの商品情報、日本語タイトル候補、Amazonの検索結果、類似度、想定仕入れ価格）を `shopee-product-filter` のUIに表示し、人間が最終判断できるようにする。

#### **5. 最終的なUI/UX**

*   `shopee-product-filter` のStreamlit UIを拡張し、上記すべての情報を一元的に表示・操作できるようにします。
*   人間が「同じ商品かどうか」と「想定通りの利益が確保できるか」を効率的に判断できるような表示形式を検討します。