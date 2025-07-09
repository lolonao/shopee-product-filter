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
    - sold_countを取得する。
    - 画像URLをCDN形式に変換する。
    - ショップタイプを判定する。
    - ロケーションを取得する（必須項目）。
    - リストのタイプ（ショップ、検索/カテゴリー、汎用）を判定・表示する。
    - 各フィールドの抽出でエラーが発生しても、可能な限り処理を続行する。
    - 抽出件数を先頭5件に限定する。
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
    # 商品リストのタイプを判定し、アイテムのリストを取得
    # ショップの商品リスト
    shop_items = soup.select('div.shop-search-result-view > div.row > div.shop-search-result-view__item')
    # キーワード検索 と カテゴリー別 の商品リスト (同じセレクタを使用)
    search_category_items = soup.select('li.col-xs-2-4.shopee-search-item-result__item')
    # data-sqe="item" の商品リスト (汎用的なセレクタ) - これが最も一般的かも
    data_sqe_items = soup.select('li[data-sqe="item"]')


    if shop_items:
        items = shop_items
    elif search_category_items: # キーワード検索とカテゴリー別のリストに対応
        items = search_category_items
    elif data_sqe_items:
        items = data_sqe_items
    else:
        print(f"エラー: 商品リストの抽出箇所を特定できませんでした。({html_file_path})")
        return None # 商品リストが見つからなかった場合はNoneを返す

    if not items:
        print(f"情報が見つかりませんでした: 該当するアイテムがありませんでした。({html_file_path})")
        return []

    EXTRACT_MAX = 500  # 最大抽出件数

    # 抽出件数を先頭5件に限定
    items_to_process = items[:EXTRACT_MAX]
    print(f"合計 {len(items)} 個のアイテムが見つかりましたが、先頭 {len(items_to_process)} 件のみ抽出します。")


    for i, item in enumerate(items_to_process):
        # print(f"  アイテム {i+1}/{len(items_to_process)} を処理中...")
        product_info: Dict[str, Optional[Union[str, float, int]]] = {
            "product_name": None,
            "price": None,
            "currency": None,
            "image_url": None,
            "product_url": None,
            "location": None, # 必須
            "sold": 0, # 必須, Default value
            "shop_type": None, # 必須, Default determined later
            # rating および discount は抽出しないため、ここでは初期化しない
        }

        # --- Extract Product URL (必須) ---
        try:
            link_tag = item.select_one('a.contents')
            if link_tag:
                 href_value = link_tag.get('href')
                 if isinstance(href_value, str):
                      product_info['product_url'] = href_value
        except Exception as e:
            print(f"  アイテム {i+1}: product_url 抽出中にエラーが発生しました: {e}")

        # --- Extract Image URL (必須) ---
        # naoさんが取得できているとのことなので、前回の最も頑丈にしたロジックを維持
        try:
            image_url = None
            main_img_tag = None

            # 1. Prioritize image within the main product link (a.contents)
            link_tag = item.select_one('a.contents')
            if link_tag:
                 main_img_tag = link_tag.select_one('img[src], img[data-src]') # Look for src or data-src inside the link

            # 2. If not found in link, try other common places with specific selectors
            if not main_img_tag:
                 main_img_tag = item.select_one('div.w-full.relative > img.inset-y-0:not([alt*="custom-overlay"]):not([alt="flag-label"])')
            if not main_img_tag:
                 main_img_tag = item.select_one('div.relative.z-0.w-full.pt-full > img')
            if not main_img_tag:
                 # Sometimes image is directly under the item div or a common container
                 main_img_tag = item.select_one('div.shopee-search-item-result__item__info img')
                 if not main_img_tag:
                      main_img_tag = item.select_one('div.shop-search-result-view__item__info img')


            # 3. If still not found, try a more general img selector within the item (heuristic)
            #    Filter out known icons or non-product images
            if not main_img_tag:
                 all_imgs = item.select('img[src], img[data-src]') # Look for src or data-src
                 for img in all_imgs:
                      src_candidate = img.get('src') or img.get('data-src')
                      if isinstance(src_candidate, str) and len(src_candidate) > 10: # Basic length check
                           alt = img.get('alt', '').lower()
                           # Simple heuristic: check if alt suggests it's NOT a product image
                           if 'icon' not in alt and 'flag' not in alt and 'overlay' not in alt and 'logo' not in alt and 'qr code' not in alt:
                                # Check src/data-src pattern - avoid very short or clearly non-product image URLs
                                if not src_candidate.startswith('data:') and not src_candidate.endswith('.svg') and not src_candidate.endswith('.gif'):
                                     # Check if the src looks like a Shopee product image URL fragment
                                     if '/file/' in src_candidate or 'img.susercontent.com' in src_candidate: # Check for domain part too
                                          main_img_tag = img
                                          break # Take the first plausible one

            # 4. Process the found image tag's src or data-src
            if main_img_tag:
                src = main_img_tag.get('src')
                if not src: # If src is empty or missing, try data-src
                     src = main_img_tag.get('data-src')

                if isinstance(src, str) and src: # Ensure src is a non-empty string
                    # Handle different URL formats
                    if src.startswith('http'):
                        image_url = src # Use full URL directly
                    elif src.startswith('//'): # Handle protocol-relative URLs
                        image_url = 'https:' + src
                    elif src.startswith('/file/'): # Specific Shopee CDN root-relative pattern
                        # Extract the path after /file/ and prepend base URL
                        # Use regex for more robustness in extracting the path segment
                        match = re.search(r'/file/([a-zA-Z0-9_-]+(?:/[^/]+)?\.\w+)$', src)
                        if match:
                             image_filename_with_path = match.group(1)
                             image_url = f"{SHOPEE_SG_IMAGE_BASE_URL}{image_filename_with_path}"
                        # Add handling for other known root-relative patterns if necessary

                    # Handle relative paths (e.g., just "filename.webp" or "path/to/filename.webp")
                    # Assume these might be relative to the CDN base URL path.
                    if image_url is None: # If not handled by the above patterns
                         try:
                             # Try to extract filename and use base URL
                             image_filename = os.path.basename(src)
                             if image_filename and '.' in image_filename and len(image_filename) > 3:
                                  # Basic check if the filename looks like a potential CDN asset name
                                   if re.match(r'^[a-zA-Z0-9_-]+(?:_[a-zA-Z0-9]+)?\.\w+$', image_filename): # e.g., filename_tn.webp
                                        image_url = f"{SHOPEE_SG_IMAGE_BASE_URL}{image_filename}" # Prepend base URL
                                   # Consider handling paths with subdirectories if necessary, but basename loses path.
                                   # A regex approach might be better for complex relative paths if the structure is known.
                                   # For now, basename + base URL heuristic for simple filenames.
                         except Exception: pass # Handle potential error in os.path.basename


            product_info['image_url'] = image_url # image_url will be None if not found or parsed
        except Exception as e:
            print(f"  アイテム {i+1}: image_url 抽出中にエラーが発生しました: {e}")


        # --- Extract Location (必須) ---
        try:
            location = None
            # 1. Try the primary selector (known class structure) - Corrected escaping
            location_tag = item.select_one('div.flex.items-center.space-x-1.max-w-full span.ml-\\[3px\\]')
            if isinstance(location_tag, Tag):
                 location = location_tag.get_text(strip=True)

            # 2. If not found, try finding the location icon and getting text next to it
            if location is None:
                 location_icon = item.select_one('img[alt="location-icon"]')
                 if location_icon:
                      # Get the parent or sibling element containing the location text
                      # Look for a span or div near the icon within the parent or nearby siblings
                      location_candidates = [location_icon.find_parent()] + location_icon.find_parents(limit=2) + location_icon.find_next_siblings(limit=2)
                      for container in location_candidates:
                           if container and isinstance(container, Tag):
                                text = container.get_text(strip=True)
                                # Clean text to remove icon's alt text if present
                                text = text.replace(location_icon.get('alt', ''), '').strip()
                                # Basic heuristic: text is short and contains letters/spaces
                                if text and 1 < len(text) < 50 and re.search(r'[a-zA-Z\s]', text):
                                     location = text # Found a plausible location text
                                     break # Take the first plausible one


            # 3. If still not found, try finding elements with class names suggesting location or shipping in common areas
            if location is None:
                # Look in the main item div, footer, etc.
                location_candidates = item.select('div[class*="location"], span[class*="location"], div[class*="shipping"], span[class*="shipping"], div.shopee-item-card__footer span, div.shopee-item-card__footer div') # Look in various places
                for candidate in location_candidates:
                     text = candidate.get_text(strip=True)
                     # Simple heuristic: text is short, contains letters/spaces, and doesn't look like sold count, rating, discount, price
                     if text and 1 < len(text) < 50 and re.search(r'[a-zA-Z\s]', text):
                          text_lower = text.lower()
                           # Exclude text containing "sold", "%", looks purely numeric (rating), or looks like price
                          if "sold" not in text_lower and "%" not in text_lower and not re.match(r'^\d+(\.\d+)?$', text) and not re.search(r'[$€£¥]', text):
                               # Further check: exclude text that is clearly just a product count or similar
                               if not re.match(r'^\d+ / \d+$', text): # e.g., "1 / 5"
                                   location = text # Found a plausible location text
                                   break # Take the first plausible one


            product_info['location'] = location # location will be None if not found by any method
        except Exception as e:
            print(f"  アイテム {i+1}: location 抽出中にエラーが発生しました: {e}")


        # --- Extract Product Name (必須) and Shop Type (必須) ---
        # Shop type flag is usually near the name, extract together for context
        try:
            product_name = None
            shop_type = 'Standard' # Default shop type
            name_div = item.select_one('div.line-clamp-2') # Common selector for name container
            if not name_div: # Try alternative name container selectors
                 name_div = item.select_one('div[class*="name"], div[class*="Name"]')

            if name_div:
                # Product Name
                name_text = name_div.get_text(strip=True)
                # Remove potential shop type text like "[Preferred]" with optional surrounding space, case-insensitive
                name_text = re.sub(r'\s*\[(Preferred|Mall|Official Store)\]\s*', '', name_text, flags=re.IGNORECASE).strip()
                product_name = name_text if name_text else None

                # Shop Type (based on flag image near the name or within the item)
                preferred_mall_suffix = None
                # Look for flag image inside or near the name container
                shop_type_img = name_div.select_one('img[alt="flag-label"]')
                if not shop_type_img:
                     # Try looking directly within the item if not in name_div
                     shop_type_img = item.select_one('img[alt="flag-label"]')
                if not shop_type_img:
                     # Try looking for images with alt attributes containing "Preferred" or "Mall" or "Official Store"
                     shop_type_img = item.select_one('img[alt*="Preferred"], img[alt*="Mall"], img[alt*="Official Store"]')


                if shop_type_img:
                    img_src = shop_type_img.get('src')
                    if isinstance(img_src, str):
                        try:
                            filename = os.path.basename(img_src)
                            base_name = os.path.splitext(filename)[0]
                            # Match suffixes
                            match = re.search(r'-([a-zA-Z0-9]+)$', base_name)
                            if match:
                                preferred_mall_suffix = match.group(1)
                            # Also check for known suffixes if the filename ends with them
                            elif base_name.endswith(PREFERRED_SRC_SUFFIX):
                                preferred_mall_suffix = PREFERRED_SRC_SUFFIX
                            elif base_name.endswith(MALL_SRC_SUFFIX):
                                preferred_mall_suffix = MALL_SRC_SUFFIX
                            elif base_name.endswith(OFFICIAL_STORE_SUFFIX):
                                preferred_mall_suffix = OFFICIAL_STORE_SUFFIX


                            # Determine shop type based on suffix
                            if preferred_mall_suffix == PREFERRED_SRC_SUFFIX:
                                shop_type = 'Preferred'
                            elif preferred_mall_suffix == MALL_SRC_SUFFIX:
                                shop_type = 'Mall'
                            elif preferred_mall_suffix == OFFICIAL_STORE_SUFFIX:
                                shop_type = 'Official Store'
                            # Default 'Standard' is already set
                        except Exception as img_e:
                             pass # Suppress frequent image processing errors unless crucial

            product_info['product_name'] = product_name
            product_info['shop_type'] = shop_type # Will be 'Standard' if not found/determined

        except Exception as e:
            print(f"  アイテム {i+1}: product_name/shop_type 抽出中にエラーが発生しました: {e}")
            # Ensure default shop_type is set even on error
            if product_info['shop_type'] is None:
                 product_info['shop_type'] = 'Standard'


        # --- Extract Price (必須) and Currency (必須) ---
        try:
            price = None
            currency = None
            # Try common price/currency container first
            price_container = item.select_one('div.truncate.flex.items-baseline')
            if price_container:
                # Currency (usually the first span in this container)
                currency_tag = price_container.select_one('span:nth-of-type(1)')
                currency = currency_tag.get_text(strip=True) if currency_tag else None

                # Price (usually the second span in this container)
                price_span = price_container.select_one('span:nth-of-type(2)')
                if price_span:
                    try: price = float(price_span.get_text(strip=True).replace(',', ''))
                    except (ValueError, TypeError): pass

            # If price wasn't found, try alternative common selectors
            if price is None:
                 alt_price_span = item.select_one('span.shopee-price-range__current-price')
                 if alt_price_span:
                      try: price = float(alt_price_span.get_text(strip=True).replace(',', ''))
                      except (ValueError, TypeError): pass

            # Try a more general price text pattern if still not found (heuristic)
            if price is None:
                 # Look for text containing numbers and currency symbols in common price areas
                 price_candidates = item.select('div.truncate.flex.items-baseline, span.shopee-price-range__current-price, div[class*="price"], div[class*="Price"], div[class*="Price"] span, div[class*="ProductCard"] div[class*="Price"], div[class*="item-card"] div[class*="price"]') # Added more containers
                 for candidate in price_candidates:
                      text = candidate.get_text(strip=True)
                      # Simple heuristic: text contains currency or number and currency-like pattern
                      if text and 1 < len(text) < 30 and (re.search(r'[$€£¥]\s*[\d,.]+', text) or re.search(r'[\d,.]+\s*[$€£¥]', text) or re.search(r'[\d,.]+', text)): # Match just numbers as a last resort if currency is found nearby?
                            # Extract number and currency from this text
                            num_match = re.search(r'[\d,.]+', text.replace(',', ''))
                            currency_match = re.search(r'[$€£¥]', text)
                            if num_match:
                                try:
                                    price = float(num_match.group(0))
                                    # If currency wasn't found by primary method, try to find it in this text
                                    if currency_match and currency is None:
                                         currency = currency_match.group(0)
                                    break # Found a price, stop searching
                                except (ValueError, TypeError):
                                    pass

            product_info['price'] = price
            # Apply currency conversion after trying to get currency
            product_info['currency'] = "SGD" if currency == "$" else currency if currency is not None else None


        except Exception as e:
            print(f"  アイテム {i+1}: price/currency 抽出中にエラーが発生しました: {e}")


        # --- Extract Sold Count (必須) ---
        try:
            sold_count_value = 0 # Default value
            # Try primary sold count selectors
            sold_div = item.select_one('div.truncate.text-shopee-black87.text-xs')
            if not sold_div: # Try alternative
                 sold_div = item.select_one('div.shopee-item-card__footer > div:last-child')
            # Add more alternative sold count selectors if needed
            if not sold_div:
                 # Look for text "sold" in common areas like footer spans/divs
                 sold_candidates = item.select('div.shopee-item-card__footer span, div.shopee-item-card__footer div, span, div')
                 for candidate in sold_candidates:
                      text = candidate.get_text(strip=True)
                      # Heuristic: text contains "sold" keyword
                      if "sold" in text.lower():
                           sold_div = candidate # Found a plausible sold text container
                           break # Take the first one

            if sold_div:
                sold_text = sold_div.get_text(strip=True)
                # Regex to find number before "sold", handling commas, decimals, and optional 'k'
                match = re.search(r'([\d,.]+)([kK])?\s*sold', sold_text, re.IGNORECASE)
                if match:
                    try:
                        sold_num_str = match.group(1).replace(',', '')
                        sold_num = float(sold_num_str)
                        # Handle 'k' suffix
                        if match.group(2):
                             sold_num *= 1000
                        sold_count_value = int(sold_num) # Convert to integer
                    except (ValueError, TypeError):
                        # If conversion fails, keep default 0
                        pass
                # else sold_count_value remains 0

            product_info['sold'] = sold_count_value
        except Exception as e:
            print(f"  アイテム {i+1}: sold count 抽出中にエラーが発生しました: {e}")
            product_info['sold'] = 0 # Ensure default is 0 on error


        products.append(product_info)
        # print(f"  アイテム {i+1} 処理完了。") # 各アイテムの完了を表示 (詳細ログが必要なら)


    # print("全てのアイテムの処理が完了しました。") # 全アイテム処理完了を表示

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

