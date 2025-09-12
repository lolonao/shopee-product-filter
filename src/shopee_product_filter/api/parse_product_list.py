"""
調整中

商品リスト（キーワード検索、カテゴリー別、ショップ別の３種類）から、商品情報を取得する（どのリストタイプかを表示するようにする）。

キーワード検索とカテゴリー別の商品リストは、同じ抽出パターンが利用できる模様（完全に同じかどうかはチェックしていない）

以下は旧コメント
Shopeeシンガポールのショップ詳細画面に表示されている、商品リストから商品情報を取得します。
コマンドの引数に与えるHTMLファイルは、ショップ詳細画面のHTMLでないといけません。
トップ画面からのキーワード検索結果に表示されるリスト画面とは、構造が違います。
"""
import re
import os
from bs4 import BeautifulSoup
from bs4.element import Tag
from typing import List, Dict, Optional, Union
import json
import argparse
import csv

# Shopee CDNの画像ベースURL - ファイル名の前に付加
SHOPEE_SG_IMAGE_BASE_URL = "https://down-sg.img.susercontent.com/file/"

# ShopeeのPreferred/Mall/Official Storeショップを示す画像ファイル名のSuffix
PREFERRED_SRC_SUFFIX = "lyan1mv3ncw641"
MALL_SRC_SUFFIX = "lyamz1z3mayu37"
OFFICIAL_STORE_SUFFIX = "ly995hjj5h28ab"


def parse_shopee_shop_products_from_file_final(html_file_path: str) -> List[Dict[str, Optional[Union[str, float, int]]]] | None:
    """
    HTMLファイルを読み込み、商品情報を抽出する。
    - すべての可能性のあるセレクタを試し、結果を結合して全商品を取得する。
    - sold_countを取得する。
    - 画像URLをCDN形式に変換する。
    - ショップタイプを判定する。
    - ロケーションを堅牢な方法で取得する。
    - 各フィールドの抽出でエラーが発生しても、可能な限り処理を続行する。
    - rating および discount は抽出しない。
    """
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"エラー: ファイルが見つかりません - {html_file_path}")
        return []
    except Exception as e:
        print(f"エラー: ファイル読み込み中にエラーが発生しました - {html_file_path}: {e}")
        return []

    soup = BeautifulSoup(html_content, 'lxml')
    products = []

    # --- すべての可能性のあるセレクタを試し、結果を結合する ---
    items = []
    list_type = "不明"

    # 1. ショップの商品リスト
    shop_items = soup.select('div.shop-search-result-view > div.row > div.shop-search-result-view__item')
    if shop_items:
        items.extend(shop_items)
        list_type = "ショップ"
        print(f"検出されたリストタイプ: {list_type} (アイテム数: {len(shop_items)})")

    # 2. キーワード検索 と カテゴリー別 の商品リスト
    search_category_items = soup.select('li.col-xs-2-4.shopee-search-item-result__item')
    if search_category_items:
        items.extend(search_category_items)
        if list_type == "不明": list_type = "検索/カテゴリー"
        print(f"検出されたリストタイプ: 検索/カテゴリー (アイテム数: {len(search_category_items)})")

    # 3. data-sqe="item" の商品リスト (汎用) - より一般的な 'div' を使用
    data_sqe_items = soup.select('div[data-sqe="item"]')
    if data_sqe_items:
        items.extend(data_sqe_items)
        if list_type == "不明": list_type = "汎用"
        print(f"検出されたリストタイプ: 汎用 (アイテム数: {len(data_sqe_items)})")

    # --- 重複の削除 ---
    # オブジェクトは一意でないため、HTML文字列をキーにして一意性を保つ
    unique_items_dict = {str(item): item for item in items}
    items_to_process = list(unique_items_dict.values())

    if not items_to_process:
        print(f"エラー: 商品リストの抽出箇所を特定できませんでした。({html_file_path})")
        return [] # アイテムが見つからない場合は空リストを返す

    EXTRACT_MAX = 500
    print(f"合計 {len(items_to_process)} 個のユニークなアイテムが見つかりました。最大 {EXTRACT_MAX} 件まで抽出します。")
    items_to_process = items_to_process[:EXTRACT_MAX]


    for i, item in enumerate(items_to_process):
        product_info: Dict[str, Optional[Union[str, float, int]]] = {
            "product_name": None, "price": None, "currency": None,
            "image_url": None, "product_url": None, "location": None,
            "sold": 0, "shop_type": 'Standard'
        }

        # --- Extract Product URL ---
        try:
            link_tag = item.find('a', href=True)
            if link_tag:
                product_info['product_url'] = link_tag['href']
        except Exception as e:
            print(f"  アイテム {i+1}: product_url 抽出エラー: {e}")

        # --- Extract Image URL ---
        try:
            image_tag = item.find('img')
            if image_tag:
                src = image_tag.get('data-src') or image_tag.get('src')
                if isinstance(src, str):
                    if src.startswith('http'):
                        product_info['image_url'] = src
                    else:
                        # 画像ファイル名らしき部分を抽出
                        match = re.search(r'([a-zA-Z0-9_]+\.(?:jpg|jpeg|png|webp))$', src)
                        if match:
                            product_info['image_url'] = f"{SHOPEE_SG_IMAGE_BASE_URL}{match.group(1)}"
        except Exception as e:
            print(f"  アイテム {i+1}: image_url 抽出エラー: {e}")

        # --- Extract Location (堅牢化) ---
        try:
            location = None
            # 戦略1: フッター領域から探す
            footer = item.select_one('div[class*="footer"]')
            if footer:
                # フッター内の最後のdiv/spanが地名であることが多い
                location_candidates = footer.select('div, span')
                if location_candidates:
                    # 後ろから探索する（"sold"の前の要素が地名である可能性）
                    for loc_cand in reversed(location_candidates):
                        text = loc_cand.get_text(strip=True)
                        # 数字や"sold"を含まない、短いテキストを地名とみなす
                        if text and not any(char.isdigit() for char in text) and 'sold' not in text.lower() and len(text) < 30:
                            location = text
                            break
            # 戦略2: 全体から"location"という単語を含むクラスを持つ要素を探す
            if not location:
                location_tag = item.select_one('div[class*="location"]')
                if location_tag:
                    location = location_tag.get_text(strip=True)

            product_info['location'] = location
        except Exception as e:
            print(f"  アイテム {i+1}: location 抽出エラー: {e}")

        # --- Extract Product Name and Shop Type ---
        try:
            name_div = item.select_one('div.line-clamp-2, div[class*="name"], div[class*="Name"]')
            if name_div:
                product_info['product_name'] = name_div.get_text(strip=True)

            # Shop Type
            if item.select_one('img[src*="mall"]'):
                product_info['shop_type'] = 'Mall'
            elif item.select_one('img[src*="preferred"]'):
                product_info['shop_type'] = 'Preferred'
        except Exception as e:
            print(f"  アイテム {i+1}: product_name/shop_type 抽出エラー: {e}")

        # --- Extract Price and Currency ---
        try:
            price_text_candidates = item.select('div[class*="price"]')
            price_text = ""
            if price_text_candidates:
                price_text = price_text_candidates[-1].get_text(strip=True) # 最も内側の価格表示を選ぶ

            if price_text:
                price_match = re.search(r'([\d,.]+)', price_text)
                if price_match:
                    product_info['price'] = float(price_match.group(1).replace(',', ''))

                currency_match = re.search(r'([$RM¥])', price_text) # Add more currency symbols if needed
                if currency_match:
                    product_info['currency'] = "SGD" if currency_match.group(1) == "$" else currency_match.group(1)
                elif product_info['price'] is not None: # 価格が見つかればデフォルト通貨を設定
                    product_info['currency'] = 'SGD' # Default to SGD
        except Exception as e:
            print(f"  アイテム {i+1}: price/currency 抽出エラー: {e}")

        # --- Extract Sold Count ---
        try:
            sold_text = ""
            sold_candidates = item.select('div, span')
            for cand in sold_candidates:
                text = cand.get_text(strip=True)
                if 'sold' in text.lower():
                    sold_text = text
                    break

            if sold_text:
                match = re.search(r'([\d,.]+)([kK])?', sold_text)
                if match:
                    num = float(match.group(1).replace(',', ''))
                    if match.group(2) and match.group(2).lower() == 'k':
                        num *= 1000
                    product_info['sold'] = int(num)
        except Exception as e:
            print(f"  アイテム {i+1}: sold count 抽出エラー: {e}")

        products.append(product_info)

    return products

# ★★★ 新しい関数: CSVファイル書き出し ★★★
def write_to_csv(data: List[Dict[str, Optional[Union[str, float, int]]]], csv_file_path: str):
    """
    商品情報のリストをCSVファイルに書き出す。

    Args:
        data: 商品情報の辞書のリスト。
        csv_file_path: 出力するCSVファイルのパス。
    """
    if not data:
        print("CSV書き出し: データが空のため、ファイルは作成されませんでした。")
        return

    # CSVのカラム名を定義 (JSON出力のキーに対応)
    # rating および discount は抽出しないため、fieldnames から削除
    fieldnames = [
        "product_name",
        "price",
        "currency",
        "image_url",
        "product_url",
        "location",
        "sold",
        "shop_type",
        # "rating", # 削除
        # "discount", # 削除
    ]

    try:
        with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            # ヘッダー行を書き込む
            writer.writeheader()

            # データ行を書き込む
            for row in data:
                # Noneは空文字列に変換して書き込む (CSVで'None'と表示されないように)
                cleaned_row = {k: '' if v is None else v for k, v in row.items()}
                writer.writerow(cleaned_row)

        print(f"CSVファイルが正常に書き出されました: {csv_file_path}")

    except Exception as e:
        print(f"CSVファイル書き出し中にエラーが発生しました - {csv_file_path}: {e}")


# ★★★ 新しい関数: JSONファイル書き出し ★★★
def write_to_json(data: List[Dict[str, Optional[Union[str, float, int]]]], json_file_path: str):
     """
     商品情報のリストをJSONファイルに書き出す。

     Args:
         data: 商品情報の辞書のリスト。
         json_file_path: 出力するJSONファイルのパス。
     """
     if not data:
         print("JSON書き出し: データが空のため、ファイルは作成されませんでした。")
         return

     try:
         # JSON書き出し時に rating と discount を含めないように、一旦新しい辞書を作成
         data_to_dump = []
         for item in data:
              cleaned_item = {k: v for k, v in item.items() if k not in ['rating', 'discount']}
              data_to_dump.append(cleaned_item)

         with open(json_file_path, 'w', encoding='utf-8') as jsonfile:
             # JSON形式で整形して書き出す
             json.dump(data_to_dump, jsonfile, ensure_ascii=False, indent=4)

         print(f"JSONファイルが正常に書き出されました: {json_file_path}")

     except Exception as e:
         print(f"JSONファイル書き出し中にエラーが発生しました - {json_file_path}: {e}")


# ★★★ メイン処理 ★★★
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Shopeeの商品リストHTMLから商品情報を抽出するスクリプト')
    parser.add_argument('html_file_path', help='処理するHTMLファイルのパス')
    parser.add_argument('--output_csv', help='結果をCSVファイルに書き出す場合のパス')
    parser.add_argument('--output_json', help='結果をJSONファイルに書き出す場合のパス')

    args = parser.parse_args()

    print(f"--- 処理開始: {args.html_file_path} ---") # 処理開始を示すメッセージ

    # HTMLファイルを指定して抽出関数を呼び出す
    products_list = parse_shopee_shop_products_from_file_final(args.html_file_path)

    print("\n--- 抽出結果 ---") # 結果表示の前に区切り線

    if products_list is not None: # products_list が None (リストコンテナが見つからなかった場合) も考慮
        if products_list:
            # 表示件数に合わせてメッセージを変更
            print(f"先頭 {len(products_list)} 件の商品情報が抽出されました。")
            # 結果を表示
            for i, product in enumerate(products_list):
                print(f"  アイテム {i+1}:")
                # JSON形式で整形して表示 (ratingとdiscountを含めない)
                cleaned_product_for_display = {k: v for k, v in product.items() if k not in ['rating', 'discount']}
                print(json.dumps(cleaned_product_for_display, ensure_ascii=False, indent=4))
        else:
            print("商品情報は抽出されませんでした。")

        # CSVファイルに書き出し (指定がある場合)
        if args.output_csv:
            write_to_csv(products_list, args.output_csv) # write_to_csv 関数内で rating/discount を除外するように修正済み

        # JSONファイルに書き出し (指定がある場合)
        if args.output_json:
             write_to_json(products_list, args.output_json) # write_to_json 関数内で rating/discount を除外するように修正済み
    else:
        print("商品リストの解析に失敗しました（リストのコンテナが見つかりませんでした）。")
    print("--- 処理終了 ---") # 処理終了を示すメッセージ