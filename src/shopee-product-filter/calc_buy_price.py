#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "bs4>=0.0.2",
#   "logging>=0.4.9.6",
#   "pandas>=2.2.3",
#   "requests>=2.32.3",
#   "yfinance>=0.2.55",
# ]
# [dependency-groups]
#   dev = [
#     "icecream>=2.1.4",
#     "pytest>=8.3.5",
#   ]
# ///
"""
Command-line interface for Shopee Price Calculator.

This module provides the CLI interface for calculating the minimum purchase price
in Japan for products sold on Shopee Singapore.

このモジュールは、Shopeeシンガポールで販売されている商品の日本での最低購入価格を計算するためのCLIインターフェイスを提供します。
を計算するためのCLIインターフェースを提供します。

[スクリプトの実行 | uv](https://docs.astral.sh/uv/guides/scripts/)
"""

import argparse
import sys
import json
import textwrap
# from .calculator import calculate_minimum_purchase_price
from calculator import calculate_minimum_purchase_price


class CustomArgumentParser(argparse.ArgumentParser):
    """
    カスタムArgumentParserクラス

    より分かりやすいエラーメッセージを提供するためのカスタムクラス
    """

    def error(self, message):
        """
        エラーメッセージをカスタマイズして表示する関数

        Args:
            message (str): 元のエラーメッセージ
        """
        self.print_usage(sys.stderr)

        # エラーメッセージをカスタマイズ
        if "required: price, weight" in message:
            err_msg = "エラー: 販売価格と商品重量の両方を指定してください。"
            example = "\n使用例: shopee-calc 50 0.5"
        elif "expected one argument" in message:
            err_msg = "エラー: 引数が不足しています。販売価格と商品重量の両方を指定してください。"
            example = "\n使用例: shopee-calc 50 0.5"
        elif "unrecognized arguments" in message:
            err_msg = "エラー: 不明な引数が指定されています。"
            example = "\n使用例: shopee-calc 50 0.5 [--json]"
        elif "argument price" in message and "invalid" in message:
            err_msg = "エラー: 販売価格は数値で指定してください。"
            example = "\n使用例: shopee-calc 50 0.5"
        elif "argument weight" in message and "invalid" in message:
            err_msg = "エラー: 商品重量は数値（キログラム）で指定してください。"
            example = "\n使用例: shopee-calc 50 0.5"
        else:
            err_msg = f"エラー: {message}"
            example = "\n使用例: shopee-calc 50 0.5 [--json]"

        # エラーメッセージと使用例を表示
        self.exit(2, f"{err_msg}{example}\n\n詳細なヘルプは「shopee-calc --help」で確認できます。\n")


def parse_args(args=None):
    """
    コマンドライン引数をパースする関数

    Args:
        args (list, optional): コマンドライン引数のリスト。デフォルトはNone（sys.argvが使用される）

    Returns:
        argparse.Namespace: パースされた引数
    """
    # カスタムパーサーを使用
    parser = CustomArgumentParser(
        description="Shopeeシンガポールの商品価格から日本での最低仕入れ価格を計算します。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        使用例:
          shopee-calc 50 0.5          # 50 SGDで販売されている0.5kgの商品の最低仕入れ価格を計算
          shopee-calc 50 0.5 --json   # 結果をJSON形式で出力
        """)
    )

    parser.add_argument(
        "price",
        type=float,
        help="Shopeeシンガポールでの販売価格（SGD）- 例: 50",
    )

    parser.add_argument(
        "weight",
        type=float,
        help="商品の重量（キログラム）- 例: 0.5",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="結果をJSON形式で出力します",
    )

    return parser.parse_args(args)


def format_output(result, json_output=False):
    """
    計算結果を整形して出力する関数

    Args:
        result (dict): 計算結果
        json_output (bool): JSON形式で出力するかどうか

    Returns:
        str: 整形された出力文字列
    """
    if json_output:
        return json.dumps(result, ensure_ascii=False, indent=2)

    # 通常の出力形式
    output = [
        "===== Shopee価格計算結果 =====",
        f"シンガポール販売価格: {result['selling_price_sgd']:.2f} SGD",
        f"日本円換算: {result['selling_price_jpy']:.0f} JPY",
        f"為替レート: {result['exchange_rate']:.2f} JPY/SGD",
        f"商品重量: {result['weight_kg']} kg",
        f"SLS送料: {result['sls_fee']} JPY",
        f"国内送料: {result['domestic_shipping_fee']} JPY",
        f"Shopee手数料: {result['shopee_fee']:.0f} JPY ({result['country_fee_rate']*100:.1f}%)",
        f"想定利益: {result['profit']:.0f} JPY ({result['profit_margin']*100:.1f}%)",
        "-----------------------------",
        f"最低仕入れ価格: {result['minimum_purchase_price_jpy']:.0f} JPY",
        f"最低仕入れ価格: {result['minimum_purchase_price_sgd']:.2f} SGD",
        "=============================",
    ]

    return "\n".join(output)


def main(args=None):
    """
    メイン関数

    Args:
        args (list, optional): コマンドライン引数のリスト。デフォルトはNone（sys.argvが使用される）

    Returns:
        int: 終了コード
    """
    try:
        # 引数をパース
        parsed_args = parse_args(args)

        # 値の検証
        if parsed_args.price <= 0:
            raise ValueError("販売価格は0より大きい値を指定してください。")

        if parsed_args.weight <= 0:
            raise ValueError("商品重量は0より大きい値を指定してください。")

        # 最低仕入れ価格を計算
        result = calculate_minimum_purchase_price(
            parsed_args.price,
            parsed_args.weight,
        )

        # 結果を出力
        print(format_output(result, parsed_args.json))

        return 0

    except ValueError as e:
        print(f"エラー: {e}", file=sys.stderr)
        print("\n使用例: shopee-calc 50 0.5 [--json]", file=sys.stderr)
        print("\n詳細なヘルプは「shopee-calc --help」で確認できます。", file=sys.stderr)
        return 1

    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}", file=sys.stderr)
        print("\n使用例: shopee-calc 50 0.5 [--json]", file=sys.stderr)
        print("\n詳細なヘルプは「shopee-calc --help」で確認できます。", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
