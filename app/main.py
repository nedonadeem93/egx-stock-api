import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .egx_analysis import EGXAnalysisProvider
from .models import (
    BulkAnalysisError,
    BulkTechnicalAnalysisResponse,
    HealthResponse,
    HistoryResponse,
    PivotPointsResponse,
    QuoteResponse,
    SearchResponse,
    SupportResistanceResponse,
    TechnicalAnalysisResponse,
)
from .provider import MarketDataError, YahooFinanceProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("stock-market-api")
settings = get_settings()
provider = YahooFinanceProvider(settings)
egx_provider = EGXAnalysisProvider(settings)
dashboard_path = Path(__file__).resolve().parents[3] / "index.html"


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting %s", settings.app_name)
    yield
    logger.info("Stopping %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "A provider-neutral API for current stock quotes, historical OHLCV candles, "
        "and symbol search, plus technical analysis for Egyptian Exchange symbols. "
        "Market data is fetched from Yahoo Finance."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False, tags=["system"])
async def root() -> FileResponse:
    return FileResponse(dashboard_path, media_type="text/html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


@app.get("/healthz", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(
        service=settings.app_name,
        version=settings.app_version,
        provider=f"{provider.provider_name}; {egx_provider.provider_name}",
    )


@app.get("/quotes/{symbol}", response_model=QuoteResponse, tags=["market data"])
async def get_quote(symbol: str) -> QuoteResponse:
    try:
        return await provider.quote(symbol)
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get(
    "/egx/{symbol}/support-resistance",
    response_model=SupportResistanceResponse,
    tags=["EGX technical analysis"],
)
async def get_egx_support_resistance(
    symbol: str,
    range_: Annotated[
        str,
        Query(alias="range", pattern=r"^(1mo|3mo|6mo|1y|2y|5y|max)$"),
    ] = "6mo",
    interval: Annotated[
        str,
        Query(pattern=r"^(1d|1wk|1mo)$"),
    ] = "1d",
    swing_window: Annotated[int, Query(ge=2, le=20)] = 5,
) -> SupportResistanceResponse:
    try:
        return await egx_provider.support_resistance(
            symbol, range_, interval, swing_window
        )
    except (MarketDataError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get(
    "/egx/{symbol}/pivot-points",
    response_model=PivotPointsResponse,
    tags=["EGX technical analysis"],
)
async def get_egx_pivot_points(
    symbol: str,
    range_: Annotated[
        str,
        Query(alias="range", pattern=r"^(1mo|3mo|6mo|1y|2y|5y|max)$"),
    ] = "3mo",
    interval: Annotated[
        str,
        Query(pattern=r"^(1d|1wk|1mo)$"),
    ] = "1d",
) -> PivotPointsResponse:
    try:
        analysis = await egx_provider.technical_analysis(symbol, range_, interval, 5)
        return PivotPointsResponse(
            symbol=analysis.symbol,
            yahoo_symbol=analysis.yahoo_symbol,
            range=analysis.range,
            interval=analysis.interval,
            current_price=analysis.current_price,
            as_of=analysis.as_of,
            pivots=analysis.pivots,
        )
    except (MarketDataError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get(
    "/egx/{symbol}/technical-analysis",
    response_model=TechnicalAnalysisResponse,
    tags=["EGX technical analysis"],
)
async def get_egx_technical_analysis(
    symbol: str,
    range_: Annotated[
        str,
        Query(alias="range", pattern=r"^(1mo|3mo|6mo|1y|2y|5y|max)$"),
    ] = "6mo",
    interval: Annotated[
        str,
        Query(pattern=r"^(1d|1wk|1mo)$"),
    ] = "1d",
    swing_window: Annotated[int, Query(ge=2, le=20)] = 5,
) -> TechnicalAnalysisResponse:
    try:
        return await egx_provider.technical_analysis(
            symbol, range_, interval, swing_window
        )
    except (MarketDataError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get(
    "/egx/bulk-analysis",
    response_model=BulkTechnicalAnalysisResponse,
    tags=["EGX technical analysis"],
)
async def get_bulk_egx_analysis(
    symbols: Annotated[str, Query(min_length=1, max_length=300)] = "ABUK,ADIB,AGCG",
    range_: Annotated[
        str,
        Query(alias="range", pattern=r"^(1mo|3mo|6mo|1y|2y|5y|max)$"),
    ] = "6mo",
    interval: Annotated[
        str,
        Query(pattern=r"^(1d|1wk|1mo)$"),
    ] = "1d",
    swing_window: Annotated[int, Query(ge=2, le=20)] = 5,
) -> BulkTechnicalAnalysisResponse:
    requested_symbols = [item.strip().upper() for item in symbols.split(",") if item.strip()]
    if not requested_symbols or len(requested_symbols) > 20:
        raise HTTPException(
            status_code=422,
            detail="Provide between 1 and 20 comma-separated EGX symbols",
        )
    analyses, errors = await egx_provider.bulk_analysis(
        requested_symbols, range_, interval, swing_window
    )
    return BulkTechnicalAnalysisResponse(
        requested_symbols=requested_symbols,
        analyses=analyses,
        errors=[
            BulkAnalysisError(symbol=symbol, yahoo_symbol=yahoo_symbol, error=error)
            for symbol, yahoo_symbol, error in errors
        ],
    )


@app.get("/history/{symbol}", response_model=HistoryResponse, tags=["market data"])
async def get_history(
    symbol: str,
    interval: Annotated[
        str,
        Query(pattern=r"^(1m|2m|5m|15m|30m|60m|90m|1h|1d|5d|1wk|1mo|3mo)$"),
    ] = "1d",
    range_: Annotated[
        str,
        Query(alias="range", pattern=r"^(1d|5d|1mo|3mo|6mo|1y|2y|5y|10y|ytd|max)$"),
    ] = "1mo",
) -> HistoryResponse:
    try:
        candles = await provider.history(symbol, interval, range_)
        return HistoryResponse(
            symbol=symbol.upper(),
            interval=interval,
            range=range_,
            candles=candles,
        )
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/search", response_model=SearchResponse, tags=["market data"])
async def search_symbols(
    q: Annotated[str, Query(min_length=1, max_length=80)],
) -> SearchResponse:
    try:
        results = await provider.search(q)
        return SearchResponse(query=q, results=results)
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
