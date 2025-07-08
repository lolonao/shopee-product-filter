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

def get_exchange_rate(pair, isDummy=False):
    if isDummy:
        return DUMMY_RATE

    """
    Google Financeから為替レートを取得する関数

    Args:
        pair (str): 通貨ペア（例: "SGD-JPY"）

    Returns:
        float: 為替レート

    Raises:
        ValueError: 為替レートを取得できなかった場合
    """
    url = f"https://www.google.com/finance/quote/{pair}"
    response = requests.get(url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        rate_element = soup.find("div", {"class": "YMlKec fxKbKc"})
        if rate_element:
            rate_text = rate_element.text.replace(",", "")
            return float(rate_text)
    raise ValueError(f"為替レートを取得できませんでした: {pair}")


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
