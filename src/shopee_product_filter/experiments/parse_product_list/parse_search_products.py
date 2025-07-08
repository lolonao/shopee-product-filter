import json
import argparse
import csv
from bs4 import BeautifulSoup
from bs4.element import Tag

def extract_product_info(html_file_path: str) -> list[dict]:
    """
    HTMLファイルから商品情報を抽出する関数
    """
    products: list[dict] = []
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"エラー: ファイルが見つかりません - {html_file_path}")
        return []
    except Exception as e:
        print(f"エラー: ファイル読み込み中にエラーが発生しました - {e}")
        return []

    soup = BeautifulSoup(html_content, 'lxml')
    product_items = soup.find_all('li', class_='col-xs-2-4 shopee-search-item-result__item')

    if not product_items:
        product_items = soup.select('li[data-sqe="item"]')
        if not product_items:
             print("代替セレクタでも商品アイテムが見つかりませんでした。")
             return []
        else:
             print("代替セレクタ li[data-sqe=\"item\"] で商品アイテムが見つかりました。")

    for item in product_items:
        if not isinstance(item, Tag):
            print(f"警告: 予期しない要素タイプが見つかりました: {type(item)}")
            continue

        product_info: dict = {}

        title_tag = item.select_one('div.line-clamp-2')
        product_info['product_name'] = title_tag.get_text(strip=True) if isinstance(title_tag, Tag) else None

        price_tag = item.select_one('div.truncate.flex.items-baseline > span:nth-of-type(2)')
        if isinstance(price_tag, Tag):
            price_text = price_tag.get_text(strip=True)
            try:
                product_info['price'] = float(price_text)
            except ValueError:
                product_info['price'] = None
        else:
            product_info['price'] = None

        # ★ 通貨記号を抽出
        currency_tag = item.select_one('div.truncate.flex.items-baseline > span:nth-of-type(1)')
        currency = currency_tag.get_text(strip=True) if currency_tag else None
        # ★ 通貨記号が $ なら SGD に変更
        product_info['currency'] = "SGD" if currency == "$" else currency

        SHOPEE_SG_IMAGE_BASE_URL = "https://down-sg.img.susercontent.com/file/"
        img_tag = item.select_one('div.relative.z-0.w-full.pt-full > img')
        if img_tag and isinstance(img_tag, Tag) and 'src' in img_tag.attrs:
            local_image_path = img_tag['src']
            if isinstance(local_image_path, str):
                image_filename = local_image_path.split('/')[-1]
                if image_filename:
                    product_info['image_url'] = f"{SHOPEE_SG_IMAGE_BASE_URL}{image_filename}"
            else:
                product_info['image_url'] = None
        else:
            product_info['image_url'] = None

        link_tag = item.find('a', class_='contents')
        product_info['product_url'] = link_tag['href'] if isinstance(link_tag, Tag) and link_tag.has_attr('href') else None

        location_tag = item.select_one('div.flex.items-center.space-x-1.max-w-full span.ml-\\[3px\\]')
        product_info['location'] = location_tag.get_text(strip=True) if isinstance(location_tag, Tag) else None

        sold_tag = item.select_one('div.truncate.text-shopee-black87.text-xs.min-h-4')
        if isinstance(sold_tag, Tag):
            sold_text = sold_tag.get_text(strip=True)
            sold_value = sold_text.split(" ")[0] if " " in sold_text else sold_text
            try:
                product_info['sold'] = int(sold_value)
            except ValueError:
                product_info['sold'] = None
        # ショップタイプ
        name_div = item.select_one('div.line-clamp-2')
        product_info['shop_type'] = None
        if name_div and isinstance(name_div, Tag):
            shop_type_img = name_div.find('img', recursive=False, attrs={'alt': 'flag-label'})
            if shop_type_img and isinstance(shop_type_img, Tag):
                product_info['shop_type'] = 'Preferred'
            else:
                product_info['shop_type'] = 'Standard'
        else:
            product_info['shop_type'] = None

        rating_div = item.select_one('div.flex-none.flex.items-center > div.text-shopee-black87')
        if rating_div and isinstance(rating_div, Tag):
            try:
                product_info['rating'] = float(rating_div.get_text(strip=True))
            except ValueError:
                product_info['rating'] = None
        else:
            product_info['rating'] = None

        discount_tag = item.select_one('div.truncate.bg-shopee-voucher-yellow')
        discount = discount_tag.get_text(strip=True) if isinstance(discount_tag, Tag) else None
        product_info['discount'] = discount

        if any(product_info.values()):
            products.append(product_info)
        else:
            item_str = item.prettify()[:500] if isinstance(item, Tag) else str(item)[:500]
            print(f"警告: 以下のアイテムからは情報を抽出できませんでした:\n{item_str}...")

    return products

def write_to_csv(data: list[dict], csv_file_path: str):
    """
    商品情報をCSVファイルに書き出す関数
    """
    if not data:
        print("エラー：出力する商品情報がありません。")
        return

    # CSVファイルに書き出す
    try:
        with open(csv_file_path, 'w', encoding='utf-8-sig', newline='') as csvfile:
            fieldnames = data[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for item in data:
                writer.writerow(item)
        print(f"商品情報を '{csv_file_path}' に出力しました。")
    except Exception as e:
        print(f"エラー: CSVファイルへの書き込み中にエラーが発生しました - {e}")

if __name__ == "__main__":
    # コマンドライン引数のパーサーを作成
    parser = argparse.ArgumentParser(
        description='指定されたHTMLファイルから商品情報を抽出し、JSONまたはCSV形式でファイルに出力します。',
        formatter_class=argparse.RawTextHelpFormatter
    )
    # 必須引数: 入力HTMLファイル
    parser.add_argument(
        'html_file',
        metavar='入力HTMLファイル',
        type=str,
        help='商品情報が含まれているHTMLファイルのパスを指定します。\n例: tests/1.html'
    )
    # オプション引数: 出力JSONファイル
    parser.add_argument(
        '-o', '--output',
        metavar='出力ファイル名',
        type=str,
        help='抽出結果を保存するJSONファイルのパスを指定します。\n例: extracted_products.json'
    )
    # オプション引数: 出力CSVファイル
    parser.add_argument(
        '-c', '--output_csv',
        metavar='出力CSVファイル名',
        type=str,
        help='抽出結果を保存するCSVファイルのパスを指定します。\n例: extracted_products.csv'
    )
    # オプション引数: Sold数フィルタ
    parser.add_argument(
        '-s', '--min_sold',
        metavar='最小Sold数',
        type=int,
        default=0,
        help='指定されたSold数以上の商品のみを出力します。\n例: 10'
    )
    # 引数を解析
    args = parser.parse_args()

    # 商品情報を抽出
    extracted_data = extract_product_info(args.html_file)

    if extracted_data:
        # Sold数でフィルタ
        filtered_data = []
        for item in extracted_data:
            sold = item.get('sold') or 0
            if sold >= args.min_sold:
                filtered_data.append(item)

        # JSONファイルへの出力
        if args.output:
            try:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(filtered_data, f, ensure_ascii=False, indent=4)
                print(f"商品情報を '{args.output}' に出力しました。")
            except Exception as e:
                print(f"エラー: JSONファイルへの書き込み中にエラーが発生しました - {e}")

        # CSVファイルへの出力
        if args.output_csv:
            write_to_csv(filtered_data, args.output_csv)

        # 最初の数件のデータを表示（確認用）
        print(f"抽出された商品数: {len(filtered_data)}")
        print("\n最初の数件のデータ:")
        for i, product in enumerate(filtered_data[:3]):
            print(f"--- 商品 {i+1} ---")
            print(json.dumps(product, ensure_ascii=False, indent=2))

    else:
        print(f"'{args.html_file}' から商品情報は抽出されませんでした。")
