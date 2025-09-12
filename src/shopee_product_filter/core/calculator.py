"""
Core calculation functions for Shopee Price Calculator.

This module contains the functions to calculate the minimum purchase price
in Japan for products sold on Shopee Singapore.
"""

import math
import requests
from bs4 import BeautifulSoup


# SLS送料表（シンガポール）
SG_SHIPPING_RATES = [
    {"weight": 0.1, "feeSGD": 3.6, "feeJPY": 250},
    {"weight": 0.2, "feeSGD": 3.83, "feeJPY": 276},
    {"weight": 0.3, "feeSGD": 4.06, "feeJPY": 302},
    {"weight": 0.4, "feeSGD": 4.29, "feeJPY": 328},
    {"weight": 0.5, "feeSGD": 4.52, "feeJPY": 353},
    {"weight": 0.75, "feeSGD": 7.02, "feeJPY": 634},
    {"weight": 1.0, "feeSGD": 9.52, "feeJPY": 914},
    {"weight": 1.25, "feeSGD": 12.02, "feeJPY": 1194},
    {"weight": 1.5, "feeSGD": 14.52, "feeJPY": 1474},
    {"weight": 1.75, "feeSGD": 17.02, "feeJPY": 1754},
    {"weight": 2.0, "feeSGD": 19.52, "feeJPY": 2034},
]

# 各国手数料率
COUNTRY_FEES = {
    "SG": {"commission": 0.11, "transactionFee": 0.02},
}

# デフォルト設定
DEFAULT_SETTINGS = {
    "country": "SG",  # 販売する国
    "domestic_shipping_fee": 710,  # 国内想定送料
    "desired_profit_margin": 0.1,  # 欲しい利益率
    "additional_profit_margin": 0.15,  # バウチャー・割引用の追加利益率
}

DUMMY_RATE: float = 108.77

import logging

# ロガーの設定
logger = logging.getLogger(__name__)

def get_exchange_rate(pair: str, isDummy: bool = False) -> float | None:
    """
    Google Financeから為替レートを安全に取得する。
    複数のセレクタを試し、堅牢なエラーハンドリングとロギングを行う。
    取得失敗時はValueErrorを発生させず、Noneを返す。

    Args:
        pair (str): 通貨ペア (例: "SGD-JPY")
        isDummy (bool): ダミーレートを返すかどうか

    Returns:
        float | None: 為替レート。取得失敗時はNone。
    """
    if isDummy:
        logger.info(f"ダミー為替レートを使用: {pair} = {DUMMY_RATE}")
        return DUMMY_RATE

    logger.info(f"Google Financeから為替レート取得開始: {pair}")
    url = f"https://www.google.com/finance/quote/{pair.upper()}"
    try:
        # タイムアウトを設定し、リクエストの失敗に備える
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # HTTPエラーがあれば例外を発生させる

        soup = BeautifulSoup(response.text, "html.parser")

        # 複数のCSSセレクタを試すことで、ページの変更に対する耐性を高める
        rate_element_selectors = [
            "div.YMlKec.fxKbKc",             # オリジナルのセレクタ
            "div[data-last-price]",          # より安定している可能性のあるデータ属性
            "span[jsmodel][data-entity-id]"  # もう一つの代替セレクタ
        ]

        rate_text = None
        for selector in rate_element_selectors:
            rate_element = soup.select_one(selector)
            if rate_element:
                # セレクタによってテキストの取得方法を分ける
                rate_text = rate_element.get('data-last-price') if selector == "div[data-last-price]" else rate_element.text
                if rate_text:
                    # カンマを削除し、前後の空白を除去
                    cleaned_rate_text = rate_text.replace(",", "").strip()
                    if cleaned_rate_text:
                        logger.info(f"為替レート要素発見 ({selector}): '{cleaned_rate_text}'")
                        parsed_rate = float(cleaned_rate_text)
                        logger.info(f"為替レート取得成功: {pair} = {parsed_rate}")
                        return parsed_rate

        logger.warning(f"為替レートの要素が見つかりませんでした: {pair} (URL: {url})")
        return None # すべてのセレクタで失敗した場合

    except requests.exceptions.RequestException as e:
        logger.error(f"為替レート取得中にリクエストエラー ({pair}): {e}")
        return None
    except (ValueError, TypeError) as e:
        logger.error(f"為替レートの解析/変換失敗 ({pair}): {e}")
        return None
    except Exception as e:
        logger.error(f"為替レート取得中に予期せぬエラー ({pair}): {e}", exc_info=True)
        return None


def calculate_sls_fee(weight_kg):
    """
    SLS送料を計算する関数

    Args:
        weight_kg (float): 商品の重量（キログラム）

    Returns:
        float: SLS送料（日本円）

    Raises:
        ValueError: 対応する重量帯が見つからない場合
    """
    # 指定された重量に最も近い重量帯を検索
    for rate in SG_SHIPPING_RATES:
        if rate["weight"] >= weight_kg:
            return rate["feeJPY"]
    
    # 重量が最大値を超える場合は、最後の重量帯の料金を返す
    return SG_SHIPPING_RATES[-1]["feeJPY"]


def calculate_minimum_purchase_price(selling_price_sgd, weight_kg):
    """
    最低仕入れ価格を計算する関数

    Args:
        selling_price_sgd (float): シンガポールでの販売価格（SGD）
        weight_kg (float): 商品の重量（キログラム）

    Returns:
        dict: 計算結果（最低仕入れ価格、為替レート、SLS送料など）
    """
    # 為替レートを取得
    exchange_rate = get_exchange_rate("SGD-JPY", isDummy=False)
    
    # レート取得失敗時のハンドリング
    if exchange_rate is None:
        raise ValueError("為替レートの取得に失敗したため、最低仕入れ価格を計算できません。")

    # シンガポールドルから日本円に変換
    selling_price_jpy = selling_price_sgd * exchange_rate
    
    # SLS送料を計算
    sls_fee = calculate_sls_fee(weight_kg)
    
    # 国内送料と手数料率を設定
    domestic_shipping_fee = DEFAULT_SETTINGS["domestic_shipping_fee"]
    country_fee_rate = COUNTRY_FEES["SG"]["commission"] + COUNTRY_FEES["SG"]["transactionFee"]
    profit_margin = DEFAULT_SETTINGS["desired_profit_margin"] + DEFAULT_SETTINGS["additional_profit_margin"]
    
    # Shopeeでの手数料を計算
    shopee_fee = selling_price_jpy * country_fee_rate
    
    # 利益を計算
    profit = selling_price_jpy * profit_margin
    
    # 最低仕入れ価格を計算（JPY）
    minimum_purchase_price_jpy = selling_price_jpy - shopee_fee - profit - domestic_shipping_fee - sls_fee
    
    # 最低仕入れ価格をSGDに変換
    minimum_purchase_price_sgd = minimum_purchase_price_jpy / exchange_rate
    
    # 結果を辞書として返す
    return {
        "selling_price_sgd": selling_price_sgd,
        "selling_price_jpy": selling_price_jpy,
        "exchange_rate": exchange_rate,
        "weight_kg": weight_kg,
        "sls_fee": sls_fee,
        "domestic_shipping_fee": domestic_shipping_fee,
        "shopee_fee": shopee_fee,
        "profit": profit,
        "minimum_purchase_price_jpy": minimum_purchase_price_jpy,
        "minimum_purchase_price_sgd": minimum_purchase_price_sgd,
        "country_fee_rate": country_fee_rate,
        "profit_margin": profit_margin,
    }
