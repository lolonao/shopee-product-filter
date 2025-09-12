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


def _parse_from_json_ld(soup: BeautifulSoup) -> List[Dict[str, any]]:
    """JSON-LDスクリプトタグから商品情報を抽出する内部関数"""
    products = []
    json_ld_scripts = soup.find_all('script', type='application/ld+json')
    for script in json_ld_scripts:
        try:
            data = json.loads(script.string)
            # 商品リストの場合 (@type: "ItemList")
            if data.get('@type') == 'ItemList' and 'itemListElement' in data:
                for item in data['itemListElement']:
                    product_data = item.get('item', {})
                    if product_data.get('@type') == 'Product':
                        offer = product_data.get('offers', [{}])[0]
                        products.append({
                            "product_name": product_data.get('name'),
                            "price": offer.get('price'),
                            "currency": offer.get('priceCurrency'),
                            "image_url": product_data.get('image'),
                            "product_url": product_data.get('url'),
                            "location": None, # JSON-LDからは取得が難しい場合が多い
                            "sold": 0, # JSON-LDに販売数はない
                            "shop_type": 'Standard', # JSON-LDにショップタイプはない
                        })
            # 単一商品ページの場合 (@type: "Product")
            elif data.get('@type') == 'Product':
                offer = data.get('offers', [{}])[0]
                products.append({
                    "product_name": data.get('name'),
                    "price": offer.get('price'),
                    "currency": offer.get('priceCurrency'),
                    "image_url": data.get('image'),
                    "product_url": data.get('url'),
                    "location": None,
                    "sold": 0,
                    "shop_type": 'Standard',
                })
        except (json.JSONDecodeError, AttributeError, IndexError):
            continue
    return products

def _parse_from_html_selectors(soup: BeautifulSoup) -> List[Dict[str, any]]:
    """従来のCSSセレクタベースで商品情報を抽出する内部関数"""
    products = []

    items = []
    list_type = "不明"
    shop_items = soup.select('div.shop-search-result-view > div.row > div.shop-search-result-view__item')
    search_category_items = soup.select('li.col-xs-2-4.shopee-search-item-result__item')
    data_sqe_items = soup.select('div[data-sqe="item"]')

    if shop_items:
        items.extend(shop_items)
        if list_type == "不明": list_type = "ショップ"
    if search_category_items:
        items.extend(search_category_items)
        if list_type == "不明": list_type = "検索/カテゴリー"
    if data_sqe_items:
        items.extend(data_sqe_items)
        if list_type == "不明": list_type = "汎用"

    unique_items_dict = {str(item): item for item in items}
    items_to_process = list(unique_items_dict.values())

    if not items_to_process: return []

    for item in items_to_process:
        product_info: Dict[str, Optional[Union[str, float, int]]] = {
            "product_name": None, "price": None, "currency": None, "image_url": None,
            "product_url": None, "location": None, "sold": 0, "shop_type": 'Standard'
        }
        try:
            link_tag = item.select_one('a')
            if link_tag and link_tag.has_attr('href'): product_info['product_url'] = link_tag['href']

            name_div = item.select_one('div.line-clamp-2, div[class*="name"]')
            if name_div: product_info['product_name'] = name_div.get_text(strip=True)

            price_container = item.select_one('div[class*="price"]')
            if price_container:
                price_text = price_container.get_text(strip=True)
                price_match = re.search(r'([\d,.]+)', price_text)
                if price_match: product_info['price'] = float(price_match.group(1).replace(',', ''))
                if product_info['price'] is not None: product_info['currency'] = 'SGD'

            footer = item.select_one('div[class*="footer"]')
            if footer:
                location_tag = footer.select_one('div:last-child')
                if location_tag and not any(c.isdigit() for c in location_tag.get_text(strip=True)):
                    product_info['location'] = location_tag.get_text(strip=True)

            sold_div = item.select_one('div[class*="sold"]')
            if sold_div:
                sold_text = sold_div.get_text(strip=True)
                match = re.search(r'([\d,.]+)([kK])?', sold_text)
                if match:
                    num = float(match.group(1).replace(',', ''))
                    if match.group(2) and match.group(2).lower() == 'k': num *= 1000
                    product_info['sold'] = int(num)

            if item.select_one('img[src*="mall"], div[class*="official-shop-badge"]'): product_info['shop_type'] = 'Mall'
            elif item.select_one('img[src*="preferred"]'): product_info['shop_type'] = 'Preferred'

            products.append(product_info)
        except Exception:
            continue
    return products


def parse_shopee_shop_products_from_file_final(html_file_path: str) -> List[Dict[str, Optional[Union[str, float, int]]]]:
    """
    HTMLファイルを読み込み、商品情報を抽出する。
    JSON-LDを優先し、失敗した場合はHTMLセレクタにフォールバックする。
    """
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except Exception as e:
        print(f"エラー: ファイル読み込み中にエラーが発生しました - {html_file_path}: {e}")
        return []

    soup = BeautifulSoup(html_content, 'lxml')

    # 戦略1: JSON-LDから取得を試みる
    products = _parse_from_json_ld(soup)

    # JSON-LDから取得できた場合、soldとlocationをHTMLから補完する
    if products:
        print(f"JSON-LDから {len(products)} 件の商品情報を取得。HTMLから追加情報を補完します。")

        html_item_map = {}
        all_html_items = []
        selectors = ['div.shop-search-result-view > div.row > div.shop-search-result-view__item', 'li.col-xs-2-4.shopee-search-item-result__item', 'div[data-sqe="item"]']
        for selector in selectors:
            all_html_items.extend(soup.select(selector))

        for html_item in all_html_items:
            link_tag = html_item.select_one('a')
            if link_tag and link_tag.has_attr('href'):
                href = link_tag['href']
                if href.startswith('/'): href = 'https://shopee.sg' + href
                html_item_map[href] = html_item

        for p_info in products:
            product_url = p_info.get('product_url')
            if not product_url: continue
            if product_url.startswith('/'): product_url = 'https://shopee.sg' + product_url

            matching_html_item = html_item_map.get(product_url)
            if matching_html_item:
                if not p_info.get('location'):
                    footer = matching_html_item.select_one('div[class*="footer"]')
                    if footer:
                        location_tag = footer.select_one('div:last-child')
                        if location_tag and not any(c.isdigit() for c in location_tag.get_text(strip=True)):
                            p_info['location'] = location_tag.get_text(strip=True)

                if not p_info.get('sold') or p_info.get('sold') == 0:
                    sold_div = matching_html_item.select_one('div[class*="sold"]')
                    if sold_div:
                        sold_text = sold_div.get_text(strip=True)
                        match = re.search(r'([\d,.]+)([kK])?', sold_text)
                        if match:
                            num = float(match.group(1).replace(',', ''))
                            if match.group(2) and match.group(2).lower() == 'k': num *= 1000
                            p_info['sold'] = int(num)
        return products

    print("JSON-LDからの取得に失敗、または情報がありませんでした。HTMLセレクタによる解析にフォールバックします。")
    products = _parse_from_html_selectors(soup)
    print(f"HTMLセレクタから {len(products)} 件の商品情報を取得しました。")

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