"""
Shopeeシンガポールのショップ詳細画面に表示されている、商品リストから商品情報を取得します。
コマンドの引数に与えるHTMLファイルは、ショップ詳細画面のHTMLでないといけません。
トップ画面からのキーワード検索結果に表示されるリスト画面とは、構造が違います。
"""
import re
from bs4 import BeautifulSoup
from bs4.element import Tag # ★ Tag をインポート
from typing import List, Dict, Optional, Union
import json
import argparse
import os
import csv # ★ CSVモジュールをインポート

SHOPEE_SG_IMAGE_BASE_URL = "https://down-sg.img.susercontent.com/file/"

def parse_shopee_shop_products_from_file_final(html_file_path: str) -> List[Dict[str, Optional[Union[str, float, int]]]]:
    """
    HTMLファイルを読み込み、商品情報を抽出する。
    - sold_countが0の場合、ratingを0.0とする。
    - discountを割引率(float、例: 10% off -> 0.1)で格納する。
    - 画像URLをCDN形式に変換する。
    - ショップタイプを判定する。
    """
    # (この関数の内容は前回の最終版から変更ありません)
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"エラー: ファイルが見つかりません - {html_file_path}")
        return []
    except Exception as e:
        print(f"エラー: ファイル読み込み中に問題が発生しました - {html_file_path}: {e}")
        return []

    soup = BeautifulSoup(html_content, 'lxml')
    products = []
    items = soup.select('div.shop-search-result-view > div.row > div.shop-search-result-view__item')

    PREFERRED_SRC_SUFFIX = "lyan1mv3ncw641"
    MALL_SRC_SUFFIX = "lyamz1z3mayu37"

    for item in items:
        # ★ キーの順序と名前 (sold_count -> sold) を修正し、重複を削除
        product_info: Dict[str, Optional[Union[str, float, int]]] = {
            "product_name": None,
            "price": None,
            "currency": None,
            "image_url": None,
            "product_url": None,
            "location": "Singapore", # デフォルト値設定
            "sold": 0, # ★ キー名を sold に変更、デフォルト値 0
            "shop_type": None,
            "rating": None,
            "discount": None,
        }

        try:
            link_tag = item.select_one('a.contents')
            # .get() を使用し、文字列であることを確認
            href_value = link_tag.get('href') if link_tag else None
            if isinstance(href_value, str):
                 product_info['product_url'] = href_value

            img_tag = item.select_one('div.w-full.relative > img.inset-y-0:not([alt*="custom-overlay"])')
            # .get() を使用し、文字列であることを確認してから basename を適用
            local_image_path = img_tag.get('src') if img_tag else None
            if isinstance(local_image_path, str):
                image_filename = os.path.basename(local_image_path)
                if image_filename:
                    product_info['image_url'] = f"{SHOPEE_SG_IMAGE_BASE_URL}{image_filename}"

            name_div = item.select_one('div.line-clamp-2')
            if name_div:
                # find は Tag | NavigableString | None を返す可能性があるため、Tag であることを確認
                shop_type_img_maybe = name_div.find('img', recursive=False, attrs={'alt': 'flag-label'})
                name_text = None
                # shop_type_img_maybe が Tag インスタンスであることを確認
                if isinstance(shop_type_img_maybe, Tag):
                    shop_type_img = shop_type_img_maybe # 型を明確にする
                    img_src = shop_type_img.get('src') # .get() を使用
                    # img_src が文字列であることを確認してから basename を適用
                    if isinstance(img_src, str):
                        filename = os.path.basename(img_src)
                        base_name = os.path.splitext(filename)[0]
                        if base_name.endswith(PREFERRED_SRC_SUFFIX): product_info['shop_type'] = 'Preferred'
                        elif base_name.endswith(MALL_SRC_SUFFIX): product_info['shop_type'] = 'Mall'
                        else: product_info['shop_type'] = 'Unknown Label'
                    else:
                         # src が文字列でない場合、または basename が期待通りでない場合
                         product_info['shop_type'] = 'Unknown Label' # ラベル不明とする

                    # shop_type_img が Tag であることを確認した上で next_sibling をチェック
                    if shop_type_img.next_sibling and isinstance(shop_type_img.next_sibling, str):
                        name_text = shop_type_img.next_sibling.strip()
                # shop_type_img_maybe が Tag でない場合 (img タグが見つからなかった場合)
                else:
                    product_info['shop_type'] = 'Standard'
                    # name_div が存在することは上で確認済みなので、get_text を呼べる
                    name_text = name_div.get_text(strip=True)
                if not name_text: name_text = name_div.get_text(strip=True)
                product_info['product_name'] = name_text if name_text else None

            price_span = item.select_one('div.truncate.flex.items-baseline > span:nth-of-type(2)')
            if price_span:
                try: product_info['price'] = float(price_span.get_text(strip=True))
                except (ValueError, TypeError): pass

            # ★ 通貨記号を抽出
            currency_tag = item.select_one('div.truncate.flex.items-baseline > span:nth-of-type(1)')
            currency = currency_tag.get_text(strip=True) if currency_tag else None
            # ★ 通貨記号が $ なら SGD に変更
            product_info['currency'] = "SGD" if currency == "$" else currency

            discount_rate = None
            discount_div = item.select_one('div.bg-shopee-voucher-yellow')
            if discount_div:
                discount_text = discount_div.get_text(strip=True)
                match = re.search(r'([\d.]+)\s*%\s*off', discount_text, re.IGNORECASE)
                if match:
                    try:
                        percentage = float(match.group(1))
                        discount_rate = percentage / 100.0
                    except (ValueError, TypeError): pass
            product_info['discount'] = discount_rate

            rating_value = None
            rating_div = item.select_one('div.flex-none.flex.items-center > div.text-shopee-black87')
            if rating_div:
                try: rating_value = float(rating_div.get_text(strip=True))
                except (ValueError, TypeError): pass

            sold_count_value = 0
            sold_div = item.select_one('div.truncate.text-shopee-black87.text-xs')
            if sold_div:
                sold_text = sold_div.get_text(strip=True)
                match = re.search(r'([\d,]+(?:\.\d+)?)\s*sold', sold_text, re.IGNORECASE)
                if match:
                    try:
                        sold_num_str = match.group(1).replace(',', '')
                        sold_count_value = int(float(sold_num_str))
                    except (ValueError, TypeError): pass

            # ★ sold キーに格納
            product_info['sold'] = sold_count_value
            # ★ sold キーで判定
            if product_info['sold'] == 0:
                product_info['rating'] = 0.0
            else:
                product_info['rating'] = rating_value

            # currency と location は初期値で設定済みのため削除
            # product_info['currency'] = 'SGD'
            # product_info['location'] = 'Singapore'
            products.append(product_info)

        except Exception as e:
            print(f"アイテム処理中にエラーが発生しました: {item} - {e}")
            # ★ sold キーで判定
            if product_info['sold'] == 0: product_info['rating'] = 0.0
            # currency と location は初期値で設定済み
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

    # CSVのヘッダー行を決定 (最初のデータのキーを使用)
    # データが空でないことは上でチェック済み
    headers = list(data[0].keys())

    try:
        # newline='' はWindowsでの余分な改行を防ぐため
        # encoding='utf-8-sig' はExcelで日本語などを開く際の文字化け対策
        with open(csv_file_path, 'a', newline='', encoding='utf-8-sig') as f:
            # DictWriterを使うと辞書から直接書き込めて便利
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader() # ヘッダーを書き込む
            writer.writerows(data) # 全データ行を書き込む
        print(f"結果を {csv_file_path} にCSV保存しました。")
    except IOError as e:
        print(f"エラー: CSVファイルへの書き込み中に問題が発生しました - {csv_file_path}: {e}")
    except Exception as e:
        print(f"エラー: CSV書き出し中に予期せぬ問題が発生しました: {e}")
# ★★★ 関数追加ここまで ★★★


# --- コマンドライン実行部分 ---
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Shopeeショップ（セラー）詳細ページのHTMLファイルから商品リストを抽出し、JSONまたはCSVで出力します。')
    parser.add_argument('html_file', help='パース対象のHTMLファイルパス')
    parser.add_argument('-o', '--output', help='結果をJSON形式で保存するファイルパス (指定なければ標準出力)')
    parser.add_argument('--csv', help='結果をCSV形式で保存するファイルパス')
    # ★ Sold数フィルタ用の引数を追加 ★
    parser.add_argument(
        '-s', '--min_sold',
        metavar='最小Sold数',
        type=int,
        default=0,
        help='指定されたSold数以上の商品のみを出力します。\n例: 10'
    )

    args = parser.parse_args()

    extracted_data = parse_shopee_shop_products_from_file_final(args.html_file)

    # ★ Sold数でフィルタリング ★
    filtered_data = []
    if extracted_data:
        for item in extracted_data:
            # ★ sold キーでフィルタリング
            # sold が None の場合や数値でない場合を考慮し、0 として扱う
            sold = item.get('sold') or 0
            if isinstance(sold, (int, float)) and sold >= args.min_sold:
                filtered_data.append(item)
        print(f"抽出された商品数: {len(extracted_data)} -> フィルタ後: {len(filtered_data)} (最小Sold数: {args.min_sold})")
    else:
        print("商品情報が抽出されませんでした。")


    # --- JSON出力処理 (フィルタリング後のデータを使用) ---
    if args.output:
        json_output = json.dumps(filtered_data, indent=2, ensure_ascii=False)
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(json_output)
            print(f"結果を {args.output} にJSON保存しました。")
        except Exception as e:
            print(f"エラー: JSONファイルへの書き込み中に問題が発生しました - {args.output}: {e}")
    elif not args.csv and filtered_data: # ★ JSON/CSV出力指定がなく、データがある場合のみ標準出力 ★
        json_output = json.dumps(filtered_data, indent=2, ensure_ascii=False)
        print("\n--- 抽出結果 (標準出力 - JSON) ---")
        print(json_output)

    # ★ CSV出力処理 (フィルタリング後のデータを使用) ★
    if args.csv:
        write_to_csv(filtered_data, args.csv)
