"""
容積重量計算関数追加版
- 両方の計算関数の戻り値の辞書に、テストが要求するキー（inputs, exchange_rate など）をすべて追加した。
- locals() というPythonの組み込み関数を使って、関数に渡された引数をまるごと inputs キーに格納するようにした。これはちょっとしたテクニックだ。
"""
import pandas as pd
from typing import Optional, Dict, Any
import math

from .models import AppConfig
from .exchange import ExchangeRateProvider

class PriceCalculator:
    """
    販売価格や仕入れ価格の計算を行うコアエンジン。
    """
    def __init__(self, config: AppConfig, exchange_provider: ExchangeRateProvider):
        self.config = config
        self.exchange = exchange_provider

    def find_shipping_fee(self, country_code: str, weight_kg: float, is_rebate: bool) -> float:
        """
        重量に基づいてSLS送料（円）を検索する。
        """
        if country_code not in self.config.countries:
            return 0.0

        country_settings = self.config.countries[country_code]
        shipping_rates = country_settings.shipping_rates

        fee_column = "fee_rebate" if is_rebate else "fee_no_rebate"
        
        suitable_rows = shipping_rates[shipping_rates['weight_kg'] <= weight_kg]

        if not suitable_rows.empty:
            fee = suitable_rows.iloc[-1][fee_column]
        else:
            fee = shipping_rates.iloc[0][fee_column]
            
        return float(fee)

    def calculate_volumetric_weight(self, length_cm: float, width_cm: float, height_cm: float) -> float:
        """
        商品サイズ（縦・横・高さ）から容積重量を計算する。
        """
        if length_cm <= 0 or width_cm <= 0 or height_cm <= 0:
            return 0.0
            
        raw_vol_weight = (length_cm * width_cm * height_cm) / 6000
        return math.ceil(raw_vol_weight * 100) / 100.0


    def calculate_selling_price(
        self,
        country_code: str,
        cost_price: float,
        weight_kg: float,
        domestic_shipping: float,
        profit_rate: float,
        voucher_rate: float,
        is_rebate: bool,
        # --- ここから新しい引数を追加 ---
        length_cm: float = 0.0,
        width_cm: float = 0.0,
        height_cm: float = 0.0
        # --- ここまで追加 ---
    ) -> Dict[str, Any]:
        """
        入力情報から販売価格や利益などを計算する（順算）。
        容積重量が想定重量より重い場合は、容積重量を実効重量として採用する。
        """
        inputs = locals()
        del inputs["self"]

        if country_code not in self.config.countries:
            return {"error": f"国コード '{country_code}' はサポートされていません。", "inputs": inputs}

        country = self.config.countries[country_code]
        
        commission_rate = country.commission_rate
        total_profit_rate = (profit_rate + voucher_rate) / 100.0

        # --- ここから容積重量の計算と実効重量の決定 ---
        volumetric_weight_kg = self.calculate_volumetric_weight(length_cm, width_cm, height_cm)
        effective_weight_kg = max(weight_kg, volumetric_weight_kg)
        # --- ここまで追加 ---

        # SLS送料の計算には実効重量を使用
        sls_fee = self.find_shipping_fee(country_code, effective_weight_kg, is_rebate)
        total_shipping_fee = domestic_shipping + sls_fee

        denominator = 1 - commission_rate - total_profit_rate
        if denominator <= 0:
            return {"error": "利益率と手数料の合計が100%を超えています。", "inputs": inputs}

        jpy_per_local = self.exchange.get_rate(country.currency_pair_to_jpy)
        if jpy_per_local is None:
            return {"error": f"{country.currency_code}の為替レートが取得できませんでした。", "inputs": inputs}

        selling_price_jpy = (cost_price + total_shipping_fee) / denominator
        selling_price_local = selling_price_jpy / jpy_per_local
        commission_jpy = selling_price_jpy * commission_rate
        
        profit_jpy = selling_price_jpy - cost_price - total_shipping_fee - commission_jpy

        final_profit_rate_pct = (profit_jpy / selling_price_jpy) * 100 if selling_price_jpy > 0 else 0
        
        return {
            "inputs": inputs,
            "selling_price_jpy": selling_price_jpy,
            "selling_price_local": selling_price_local,
            "exchange_rate": jpy_per_local,
            "sls_fee_jpy": sls_fee,
            "total_shipping_jpy": total_shipping_fee,
            "commission_jpy": commission_jpy,
            "commission_rate_pct": commission_rate * 100,
            "profit_jpy": profit_jpy,
            "target_profit_rate_pct": total_profit_rate * 100,
            "final_profit_rate_pct": final_profit_rate_pct,
            "currency_code": country.currency_code,
            "volumetric_weight_kg": volumetric_weight_kg,
            "effective_weight_kg": effective_weight_kg,
            "error": None,
        }

    def calculate_cost_price(
        self,
        country_code: str,
        target_selling_price_local: float,
        weight_kg: float,
        domestic_shipping: float,
        profit_rate: float,
        voucher_rate: float,
        is_rebate: bool,
        # --- ここから新しい引数を追加 ---
        length_cm: float = 0.0,
        width_cm: float = 0.0,
        height_cm: float = 0.0
        # --- ここまで追加 ---
    ) -> Dict[str, Any]:
        """
        目標販売価格から仕入れ価格の上限を計算する（逆算）。
        容積重量が想定重量より重い場合は、容積重量を実効重量として採用する。
        """
        inputs = locals()
        del inputs["self"]

        if country_code not in self.config.countries:
            return {"error": f"国コード '{country_code}' はサポートされていません。", "inputs": inputs}

        country = self.config.countries[country_code]

        jpy_per_local = self.exchange.get_rate(country.currency_pair_to_jpy)
        if jpy_per_local is None:
            return {"error": f"{country.currency_code}の為替レートが取得できませんでした。", "inputs": inputs}
        
        target_selling_price_jpy = target_selling_price_local * jpy_per_local
        
        # --- ここから容積重量の計算と実効重量の決定 ---
        volumetric_weight_kg = self.calculate_volumetric_weight(length_cm, width_cm, height_cm)
        effective_weight_kg = max(weight_kg, volumetric_weight_kg)
        # --- ここまで追加 ---

        # SLS送料の計算には実効重量を使用
        sls_fee = self.find_shipping_fee(country_code, effective_weight_kg, is_rebate)
        total_shipping_fee = domestic_shipping + sls_fee
        
        commission_jpy = target_selling_price_jpy * country.commission_rate
        total_profit_rate = (profit_rate + voucher_rate) / 100.0
        
        profit_jpy = target_selling_price_jpy * total_profit_rate

        max_cost_price = target_selling_price_jpy - total_shipping_fee - commission_jpy - profit_jpy
        max_cost_price_local = max_cost_price / jpy_per_local

        return {
            "inputs": inputs,
            "max_cost_price_jpy": max_cost_price,
            "max_cost_price_local": max_cost_price_local,
            "target_selling_price_jpy": target_selling_price_jpy,
            "exchange_rate": jpy_per_local,
            "sls_fee_jpy": sls_fee,
            "total_shipping_jpy": total_shipping_fee,
            "commission_jpy": commission_jpy,
            "profit_jpy": profit_jpy,
            "volumetric_weight_kg": volumetric_weight_kg,
            "effective_weight_kg": effective_weight_kg,
            "error": None,
        }
