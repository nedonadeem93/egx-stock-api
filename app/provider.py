from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import httpx

from .config import Settings
from .models import Candle, QuoteResponse, SearchResult


class MarketDataError(RuntimeError):
    """Raised when the upstream market data provider cannot serve a request."""


class YahooFinanceProvider:
    provider_name = "Yahoo Finance"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cache: dict[str, tuple[float, Any]] = {}

    async def _get_json(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        url = f"{self.settings.market_data_base_url.rstrip('/')}/{path.lstrip('/')}"
        cache_key = f"{url}?{sorted(params.items())}"
        now = time.monotonic()
        cached = self._cache.get(cache_key)
        if cached and now - cached[0] < self.settings.cache_ttl_seconds:
            return cached[1]

        try:
            async with httpx.AsyncClient(
                timeout=self.settings.market_data_timeout_seconds,
                headers={"User-Agent": "stock-market-api/1.0"},
            ) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MarketDataError("Market data provider is unavailable") from exc

        self._cache[cache_key] = (now, payload)
        return payload

    async def quote(self, symbol: str) -> QuoteResponse:
        normalized = symbol.upper()
        payload = await self._get_json(
            f"/v8/finance/chart/{normalized}",
            {"range": "1d", "interval": "1d", "includePrePost": "true"},
        )
        result = self._first_result(payload, normalized)
        meta = result.get("meta", {})
        price = self._number(meta.get("regularMarketPrice"))
        previous_close = self._number(
            meta.get("previousClose") or meta.get("chartPreviousClose")
        )
        change = price - previous_close if price is not None and previous_close else None
        change_percent = change / previous_close * 100 if change is not None else None
        timestamp = meta.get("regularMarketTime")

        return QuoteResponse(
            symbol=normalized,
            name=meta.get("shortName") or meta.get("longName"),
            exchange=meta.get("exchangeName"),
            currency=meta.get("currency"),
            price=price,
            previous_close=previous_close,
            change=change,
            change_percent=change_percent,
            market_state=meta.get("marketState"),
            as_of=datetime.fromtimestamp(timestamp, tz=UTC) if timestamp else None,
        )

    async def history(self, symbol: str, interval: str, range_: str) -> list[Candle]:
        normalized = symbol.upper()
        payload = await self._get_json(
            f"/v8/finance/chart/{normalized}",
            {"range": range_, "interval": interval, "includePrePost": "false"},
        )
        result = self._first_result(payload, normalized)
        timestamps = result.get("timestamp") or []
        quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
        candles: list[Candle] = []

        for index, timestamp in enumerate(timestamps):
            values = {
                key: self._number(items[index] if index < len(items) else None)
                for key, items in quote.items()
            }
            if any(values.get(key) is None for key in ("open", "high", "low", "close")):
                continue
            candles.append(
                Candle(
                    timestamp=datetime.fromtimestamp(timestamp, tz=UTC),
                    open=values["open"],
                    high=values["high"],
                    low=values["low"],
                    close=values["close"],
                    volume=int(values.get("volume") or 0),
                )
            )
        return candles

    async def search(self, query: str) -> list[SearchResult]:
        payload = await self._get_json(
            "/v1/finance/search",
            {"q": query, "quotesCount": "10", "newsCount": "0"},
        )
        results = []
        for item in payload.get("quotes", []):
            symbol = item.get("symbol")
            name = item.get("shortname") or item.get("longname")
            if symbol and name:
                results.append(
                    SearchResult(
                        symbol=symbol,
                        name=name,
                        exchange=item.get("exchange"),
                        quote_type=item.get("quoteType"),
                    )
                )
        return results

    @staticmethod
    def _first_result(payload: dict[str, Any], symbol: str) -> dict[str, Any]:
        chart = payload.get("chart") or {}
        error = chart.get("error")
        results = chart.get("result") or []
        if error or not results:
            message = (error or {}).get("description") if error else f"Symbol '{symbol}' was not found"
            raise MarketDataError(message)
        return results[0]

    @staticmethod
    def _number(value: Any) -> float | None:
        return float(value) if isinstance(value, (int, float)) else None