from __future__ import annotations

from typing import Any

import aiohttp


class BinanceClient:
    """Read-only REST adapter for Binance's public Spot market-data API.

    Verified against https://developers.binance.com/docs/binance-spot-api-docs
    on 2026-09-20. None of these endpoints require an API key or signature.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.json()

    async def book_ticker(self, symbol: str) -> dict[str, Any]:
        """GET /api/v3/ticker/bookTicker?symbol=... -> bidPrice/askPrice/etc."""
        return await self._get("/api/v3/ticker/bookTicker", {"symbol": symbol})

    async def exchange_info(self) -> dict[str, Any]:
        """GET /api/v3/exchangeInfo -> full symbols list with filters.

        Used once at startup (and periodically refreshed) to discover which
        symbols exist and their LOT_SIZE / NOTIONAL filters, not polled every
        cycle — Binance weights this endpoint heavily.
        """
        return await self._get("/api/v3/exchangeInfo")

    async def ticker_24h(self, symbol: str) -> dict[str, Any]:
        """GET /api/v3/ticker/24hr?symbol=... -> volume, lastPrice, etc."""
        return await self._get("/api/v3/ticker/24hr", {"symbol": symbol})
