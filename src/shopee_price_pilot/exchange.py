import requests
from bs4 import BeautifulSoup
import time
from typing import Dict, Optional, Tuple


class ExchangeRateProvider:
    """
    Google Financeをスクレイピングして為替レートを取得し、キャッシュするクラス。
    """

    _base_url = "https://www.google.com/finance/quote/"
    _headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    def __init__(self, cache_seconds: int = 3600):
        """
        Args:
            cache_seconds (int): キャッシュの有効期間（秒）。
        """
        self._cache: Dict[str, Tuple[float, float]] = {}
        self._cache_seconds = cache_seconds

    def _fetch_from_google(self, pair: str) -> Optional[float]:
        """Google Financeからレートをスクレイピングする内部関数"""
        # 通貨ペアを "SGD-JPY" の形式に整形
        formatted_pair = pair.replace("=X", "-JPY")
        url = f"{self._base_url}{formatted_pair}"

        try:
            response = requests.get(url, headers=self._headers, timeout=10)
            response.raise_for_status()  # 200番台以外のステータスコードで例外を発生

            soup = BeautifulSoup(response.text, "html.parser")
            rate_element = soup.find("div", {"class": "YMlKec fxKbKc"})

            if rate_element and rate_element.text:
                rate_text = rate_element.text.replace(",", "")
                return float(rate_text)

            print(f"Warning: Rate element not found for {pair} on page {url}")
            return None

        except requests.exceptions.RequestException as e:
            print(f"Error fetching exchange rate for {pair}: {e}")
            return None
        except (ValueError, AttributeError) as e:
            print(f"Error parsing exchange rate for {pair}: {e}")
            return None

    def get_rate(self, pair: str) -> Optional[float]:
        """
        指定された通貨ペアの為替レートを取得する。
        キャッシュがあればそれを使用し、なければGoogle Financeから取得する。
        """
        current_time = time.time()

        if pair in self._cache:
            rate, timestamp = self._cache[pair]
            if current_time - timestamp < self._cache_seconds:
                print(f"Cache hit for {pair}. Returning cached rate: {rate}")
                return rate

        print(f"Cache miss for {pair}. Fetching from Google Finance...")
        new_rate = self._fetch_from_google(pair)

        if new_rate is not None:
            self._cache[pair] = (new_rate, current_time)
            return new_rate

        # 取得失敗時は古いキャッシュがあればそれを返す（フォールバック）
        if pair in self._cache:
            print(f"API fetch failed for {pair}. Returning stale cache.")
            return self._cache[pair][0]

        return None


# --- DummyExchangeRateProvider をここに追加 --- 
class DummyExchangeRateProvider:
    """常に固定値を返すダミーの為替レートプロバイダー"""

    def __init__(self, fixed_rate: float):
        self._fixed_rate = fixed_rate

    def get_rate(self, pair: str) -> Optional[float]:
        print(f"Using dummy exchange rate: {self._fixed_rate} for {pair}")
        return self._fixed_rate


if __name__ == "__main__":
    # このファイルが直接実行された場合のテスト用コード
    print("--- ExchangeRateProvider (Scraping) Test ---")
    # テスト用にキャッシュを10秒に
    provider = ExchangeRateProvider(cache_seconds=10)

    # 1回目の取得 (スクレイピング)
    print("\n1. First fetch for SGD-JPY:")
    sgd_rate = provider.get_rate("SGD=X")
    print(f"  -> Got SGD-JPY rate: {sgd_rate}")

    # 2回目の取得 (キャッシュから)
    print("\n2. Second fetch for SGD-JPY (should be from cache):")
    sgd_rate_cached = provider.get_rate("SGD=X")
    print(f"  -> Got SGD-JPY rate from cache: {sgd_rate_cached}")

    # 10秒待つ
    print("\n3. Waiting 11 seconds to expire cache...")
    time.sleep(11)

    # 3回目の取得 (再度スクレイピング)
    print("\n4. Third fetch for SGD-JPY (should be from API again):")
    sgd_rate_new = provider.get_rate("SGD=X")
    print(f"  -> Got new SGD-JPY rate: {sgd_rate_new}")

    print("\n--- DummyExchangeRateProvider Test ---")
    dummy_provider = DummyExchangeRateProvider(123.45)
    dummy_rate = dummy_provider.get_rate("USD=X")
    print(f"  -> Got dummy rate: {dummy_rate}")
