import pandas as pd
from dataclasses import dataclass
from typing import Dict


# １つの国の設定情報を格納するデータクラス
@dataclass(frozen=True)
class CountrySettings:
    code: str
    currency_code: str
    currency_pair_to_jpy: str
    commission_rate: float
    shipping_rates: pd.DataFrame


# アプリケーション全体の設定情報を格納するデータクラス
@dataclass(frozen=True)
class AppConfig:
    countries: Dict[str, CountrySettings]
    api_config: Dict[str, int]
