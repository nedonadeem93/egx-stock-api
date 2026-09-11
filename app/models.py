from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    version: str
    provider: str


class QuoteResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    symbol: str
    name: str | None = None
    exchange: str | None = None
    currency: str | None = None
    price: float | None = None
    previous_close: float | None = None
    change: float | None = None
    change_percent: float | None = None
    market_state: str | None = None
    as_of: datetime | None = None


class Candle(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class HistoryResponse(BaseModel):
    symbol: str
    interval: str
    range: str
    candles: list[Candle]


class SearchResult(BaseModel):
    symbol: str
    name: str
    exchange: str | None = None
    quote_type: str | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


class TechnicalIndicators(BaseModel):
    sma_20: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    ema_20: float | None = None
    rsi_14: float | None = None
    atr_14: float | None = None
    bollinger_upper: float | None = None
    bollinger_middle: float | None = None
    bollinger_lower: float | None = None


class TechnicalLevel(BaseModel):
    price: float
    strength: int = Field(ge=1, le=5)
    sources: list[str]
    distance_percent: float | None = None


class SupportResistanceResponse(BaseModel):
    symbol: str
    yahoo_symbol: str
    range: str
    interval: str
    current_price: float
    as_of: datetime
    supports: list[TechnicalLevel]
    resistances: list[TechnicalLevel]
    indicators: TechnicalIndicators


class PivotPoints(BaseModel):
    calculated_from: datetime
    high: float
    low: float
    close: float
    pivot: float
    resistance_1: float
    resistance_2: float
    resistance_3: float
    support_1: float
    support_2: float
    support_3: float


class PivotPointsResponse(BaseModel):
    symbol: str
    yahoo_symbol: str
    range: str
    interval: str
    current_price: float
    as_of: datetime
    pivots: PivotPoints


class TechnicalAnalysisResponse(BaseModel):
    symbol: str
    yahoo_symbol: str
    range: str
    interval: str
    current_price: float
    as_of: datetime
    supports: list[TechnicalLevel]
    resistances: list[TechnicalLevel]
    pivots: PivotPoints
    indicators: TechnicalIndicators


class BulkAnalysisError(BaseModel):
    symbol: str
    yahoo_symbol: str
    error: str


class BulkTechnicalAnalysisResponse(BaseModel):
    requested_symbols: list[str]
    analyses: list[TechnicalAnalysisResponse]
    errors: list[BulkAnalysisError]