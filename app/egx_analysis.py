from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import pandas_ta as ta  # noqa: F401 - registers the DataFrame .ta accessor
import yfinance as yf

from .config import Settings
from .models import (
    PivotPoints,
    SupportResistanceResponse,
    TechnicalAnalysisResponse,
    TechnicalIndicators,
    TechnicalLevel,
)
from .provider import MarketDataError

logger = logging.getLogger("stock-market-api.egx")
_EGX_SYMBOL = re.compile(r"^[A-Z0-9]{1,12}(?:\.CA)?$")
_OHLCV_COLUMNS = ("Open", "High", "Low", "Close", "Volume")


def normalize_egx_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if normalized.endswith(".CA"):
        base = normalized[:-3]
    else:
        base = normalized
    if not base or not _EGX_SYMBOL.fullmatch(f"{base}.CA"):
        raise ValueError(
            "EGX symbols must contain 1-12 letters or numbers, optionally ending in .CA"
        )
    return f"{base}.CA"


@dataclass(frozen=True)
class AnalysisRequest:
    symbol: str
    yahoo_symbol: str
    range: str
    interval: str
    swing_window: int


class EGXAnalysisProvider:
    """Technical analysis for Egyptian Exchange tickers using yfinance and pandas_ta."""

    provider_name = "Yahoo Finance via yfinance (EGX .CA)"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cache: dict[str, tuple[float, pd.DataFrame]] = {}

    async def support_resistance(
        self,
        symbol: str,
        range_: str,
        interval: str,
        swing_window: int,
    ) -> SupportResistanceResponse:
        request, frame = await self._load(symbol, range_, interval, swing_window)
        analysis = self._calculate(request, frame)
        return SupportResistanceResponse(
            symbol=analysis.symbol,
            yahoo_symbol=analysis.yahoo_symbol,
            range=analysis.range,
            interval=analysis.interval,
            current_price=analysis.current_price,
            as_of=analysis.as_of,
            supports=analysis.supports,
            resistances=analysis.resistances,
            indicators=analysis.indicators,
        )

    async def pivot_points(
        self,
        symbol: str,
        range_: str,
        interval: str,
        swing_window: int,
    ):
        request, frame = await self._load(symbol, range_, interval, swing_window)
        analysis = self._calculate(request, frame)
        return analysis.pivots

    async def technical_analysis(
        self,
        symbol: str,
        range_: str,
        interval: str,
        swing_window: int,
    ) -> TechnicalAnalysisResponse:
        request, frame = await self._load(symbol, range_, interval, swing_window)
        return self._calculate(request, frame)

    async def bulk_analysis(
        self,
        symbols: list[str],
        range_: str,
        interval: str,
        swing_window: int,
    ) -> tuple[list[TechnicalAnalysisResponse], list[tuple[str, str, str]]]:
        async def analyze(symbol: str):
            try:
                yahoo_symbol = normalize_egx_symbol(symbol)
                return await self.technical_analysis(
                    yahoo_symbol, range_, interval, swing_window
                )
            except (MarketDataError, ValueError) as exc:
                normalized = symbol.strip().upper()
                yahoo_symbol = (
                    f"{normalized}.CA" if "." not in normalized else normalized
                )
                return (normalized, yahoo_symbol, str(exc))

        results = await asyncio.gather(*(analyze(symbol) for symbol in symbols))
        analyses = [result for result in results if isinstance(result, TechnicalAnalysisResponse)]
        errors = [result for result in results if isinstance(result, tuple)]
        return analyses, errors

    async def _load(
        self,
        symbol: str,
        range_: str,
        interval: str,
        swing_window: int,
    ) -> tuple[AnalysisRequest, pd.DataFrame]:
        yahoo_symbol = normalize_egx_symbol(symbol)
        request = AnalysisRequest(
            symbol=yahoo_symbol.removesuffix(".CA"),
            yahoo_symbol=yahoo_symbol,
            range=range_,
            interval=interval,
            swing_window=swing_window,
        )
        cache_key = f"{yahoo_symbol}:{range_}:{interval}"
        now = time.monotonic()
        cached = self._cache.get(cache_key)
        if cached and now - cached[0] < self.settings.cache_ttl_seconds:
            return request, cached[1].copy()

        try:
            frame = await asyncio.to_thread(self._download, yahoo_symbol, range_, interval)
        except Exception as exc:
            logger.warning("EGX data download failed for %s: %s", yahoo_symbol, exc)
            raise MarketDataError(f"Unable to fetch data for {yahoo_symbol}") from exc
        self._cache[cache_key] = (now, frame)
        return request, frame.copy()

    @staticmethod
    def _download(symbol: str, range_: str, interval: str) -> pd.DataFrame:
        frame = yf.download(
            symbol,
            period=range_,
            interval=interval,
            auto_adjust=False,
            progress=False,
            threads=False,
            group_by="column",
        )
        if frame is None or frame.empty:
            raise MarketDataError(f"No market data was returned for {symbol}")
        return EGXAnalysisProvider._normalize_frame(frame)

    @staticmethod
    def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
        normalized = frame.copy()
        if isinstance(normalized.columns, pd.MultiIndex):
            flattened: list[str] = []
            for column in normalized.columns:
                match = next(
                    (part for part in column if str(part) in _OHLCV_COLUMNS), None
                )
                flattened.append(str(match or column[-1]))
            normalized.columns = flattened
        normalized = normalized.loc[
            :, [column for column in _OHLCV_COLUMNS if column in normalized.columns]
        ]
        missing = [column for column in _OHLCV_COLUMNS if column not in normalized.columns]
        if missing:
            raise MarketDataError(f"Market data is missing columns: {', '.join(missing)}")
        normalized = normalized.dropna(subset=["Open", "High", "Low", "Close"])
        if normalized.empty:
            raise MarketDataError("Market data did not contain usable candles")
        return normalized

    def _calculate(
        self, request: AnalysisRequest, frame: pd.DataFrame
    ) -> TechnicalAnalysisResponse:
        working = frame.copy()
        working["SMA_20"] = _indicator(working, "sma", 20)
        working["SMA_50"] = _indicator(working, "sma", 50)
        working["SMA_200"] = _indicator(working, "sma", 200)
        working["EMA_20"] = _indicator(working, "ema", 20)
        working["RSI_14"] = _indicator(working, "rsi", 14)
        working["ATR_14"] = _indicator(working, "atr", 14)
        bands = _indicator_frame(working, "bbands", 20)
        if bands is not None and not bands.empty:
            working["BBL_20_2.0"] = bands.iloc[:, 0]
            working["BBM_20_2.0"] = bands.iloc[:, 1]
            working["BBU_20_2.0"] = bands.iloc[:, 2]

        current_price = _latest(working["Close"])
        as_of = _as_utc_datetime(working.index[-1])
        indicators = TechnicalIndicators(
            sma_20=_latest(working.get("SMA_20")),
            sma_50=_latest(working.get("SMA_50")),
            sma_200=_latest(working.get("SMA_200")),
            ema_20=_latest(working.get("EMA_20")),
            rsi_14=_latest(working.get("RSI_14")),
            atr_14=_latest(working.get("ATR_14")),
            bollinger_lower=_latest(working.get("BBL_20_2.0")),
            bollinger_middle=_latest(working.get("BBM_20_2.0")),
            bollinger_upper=_latest(working.get("BBU_20_2.0")),
        )
        supports, resistances = _levels(
            working, current_price, request.swing_window, indicators
        )
        pivots = _pivot_points(working, current_price)
        return TechnicalAnalysisResponse(
            symbol=request.symbol,
            yahoo_symbol=request.yahoo_symbol,
            range=request.range,
            interval=request.interval,
            current_price=current_price,
            as_of=as_of,
            supports=supports,
            resistances=resistances,
            pivots=pivots,
            indicators=indicators,
        )


def _latest(series: pd.Series | None) -> float | None:
    if series is None or isinstance(series, pd.DataFrame):
        return None
    values = series.dropna()
    return float(values.iloc[-1]) if not values.empty else None


def _indicator(frame: pd.DataFrame, name: str, length: int) -> pd.Series:
    if len(frame) < length:
        return pd.Series(index=frame.index, dtype="float64")
    result = getattr(frame.ta, name)(length=length)
    if isinstance(result, pd.DataFrame):
        return (
            result.iloc[:, 0]
            if result.shape[1] == 1
            else pd.Series(index=frame.index, dtype="float64")
        )
    return result


def _indicator_frame(frame: pd.DataFrame, name: str, length: int) -> pd.DataFrame:
    if len(frame) < length:
        return pd.DataFrame(index=frame.index)
    result = getattr(frame.ta, name)(length=length, std=2)
    return result if isinstance(result, pd.DataFrame) else pd.DataFrame(index=frame.index)


def _as_utc_datetime(value: Any) -> datetime:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp.to_pydatetime()


def _levels(
    frame: pd.DataFrame,
    current_price: float,
    swing_window: int,
    indicators: TechnicalIndicators,
) -> tuple[list[TechnicalLevel], list[TechnicalLevel]]:
    width = swing_window * 2 + 1
    lows = frame["Low"].rolling(width, center=True).min()
    highs = frame["High"].rolling(width, center=True).max()
    support_candidates: list[tuple[float, str]] = []
    resistance_candidates: list[tuple[float, str]] = []

    for index in frame.index:
        low = float(frame.at[index, "Low"])
        high = float(frame.at[index, "High"])
        if pd.notna(lows.at[index]) and low == float(lows.at[index]) and low < current_price:
            support_candidates.append((low, "swing_low"))
        if (
            pd.notna(highs.at[index])
            and high == float(highs.at[index])
            and high > current_price
        ):
            resistance_candidates.append((high, "swing_high"))

    moving_averages = {
        "sma_20": indicators.sma_20,
        "sma_50": indicators.sma_50,
        "sma_200": indicators.sma_200,
        "ema_20": indicators.ema_20,
        "bollinger_lower": indicators.bollinger_lower,
        "bollinger_upper": indicators.bollinger_upper,
    }
    for source, value in moving_averages.items():
        if value is None:
            continue
        if value < current_price:
            support_candidates.append((value, source))
        elif value > current_price:
            resistance_candidates.append((value, source))

    if not support_candidates:
        support_candidates.append((float(frame["Low"].tail(30).min()), "recent_low"))
    if not resistance_candidates:
        resistance_candidates.append(
            (float(frame["High"].tail(30).max()), "recent_high")
        )
    return _cluster_levels(support_candidates, current_price, reverse=True), _cluster_levels(
        resistance_candidates, current_price, reverse=False
    )


def _cluster_levels(
    candidates: list[tuple[float, str]], current_price: float, reverse: bool
) -> list[TechnicalLevel]:
    clusters: list[dict[str, Any]] = []
    for price, source in sorted(candidates, key=lambda item: item[0]):
        cluster = next(
            (
                item
                for item in clusters
                if abs(price - item["price"]) / max(item["price"], 0.01) <= 0.01
            ),
            None,
        )
        if cluster is None:
            clusters.append({"price": price, "sources": [source]})
        else:
            cluster["price"] = (cluster["price"] + price) / 2
            cluster["sources"].append(source)

    levels = [
        TechnicalLevel(
            price=round(float(cluster["price"]), 4),
            strength=min(5, len(cluster["sources"])),
            sources=cluster["sources"],
            distance_percent=round(
                abs(current_price - float(cluster["price"])) / current_price * 100, 2
            ),
        )
        for cluster in clusters
    ]
    return sorted(levels, key=lambda level: level.price, reverse=reverse)[:5]


def _pivot_points(frame: pd.DataFrame, current_price: float) -> PivotPoints:
    source = frame.iloc[-2] if len(frame) > 1 else frame.iloc[-1]
    high = float(source["High"])
    low = float(source["Low"])
    close = float(source["Close"])
    pivot = (high + low + close) / 3
    return PivotPoints(
        calculated_from=_as_utc_datetime(frame.index[-2] if len(frame) > 1 else frame.index[-1]),
        high=high,
        low=low,
        close=close,
        pivot=pivot,
        resistance_1=2 * pivot - low,
        resistance_2=pivot + high - low,
        resistance_3=high + 2 * (pivot - low),
        support_1=2 * pivot - high,
        support_2=pivot - high + low,
        support_3=low - 2 * (high - pivot),
    )