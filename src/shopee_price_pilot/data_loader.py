import json
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional

from .models import AppConfig, CountrySettings

# このファイルは src/shopee_price_pilot/ に配置されるため、プロジェクトルートはカレントワーキングディレクトリ
PROJECT_ROOT = Path.cwd()
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


def _load_json_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_shipping_rates_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Shipping rates file not found: {path}")
    return pd.read_csv(path)


def load_application_config(data_dir: Optional[Path] = None) -> AppConfig:
    if data_dir is None:
        data_dir = DEFAULT_DATA_DIR

    # 計画書でリネームした設定ファイル名を参照する
    config_path = data_dir / "price_pilot_config.json"
    raw_config = _load_json_config(config_path)

    country_settings_map: Dict[str, CountrySettings] = {}

    commission_rates = raw_config.get("commission_rates", {})
    all_currency_info = raw_config.get("currency_info", {})

    for country_code, rate in commission_rates.items():
        currency_info = all_currency_info.get(country_code)
        if not currency_info or not isinstance(currency_info, dict):
            raise ValueError(
                f"'{country_code}'の'currency_info'がconfig.jsonに見つからないか、形式が不正です。"
            )

        currency_code_val = currency_info.get("code")
        if not currency_code_val:
            raise ValueError(
                f"'{country_code}'の'currency_info'に'code'キーがありません。"
            )

        pair_to_jpy_val = currency_info.get("pair_to_jpy")
        if not pair_to_jpy_val:
            raise ValueError(
                f"'{country_code}'の'currency_info'に'pair_to_jpy'キーがありません。"
            )

        shipping_csv_path = data_dir / f"shipping_rates_{country_code.lower()}.csv"

        country_settings = CountrySettings(
            code=country_code,
            commission_rate=rate,
            currency_code=currency_code_val,
            currency_pair_to_jpy=pair_to_jpy_val,
            shipping_rates=_load_shipping_rates_csv(shipping_csv_path),
        )
        country_settings_map[country_code] = country_settings

    return AppConfig(
        countries=country_settings_map,
        api_config=raw_config.get("api", {}),
    )
