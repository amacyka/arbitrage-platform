from __future__ import annotations

from typing import Any

import aiohttp


class BybitClient:
    """Read-only REST adapter for Bybit's public v5 market-data API.

    Verified against https://bybit-exchange.github.io/docs/v5/intro on
    2026-09-20. category=spot public endpoints require no API key.
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

    async def tickers(self, symbol: str | None = None) -> dict[str, Any]:
        """GET /v5/market/tickers?category=spot[&symbol=...]

        Response: {"result": {"list": [{"symbol", "bid1Price", "ask1Price",
        "lastPrice", "volume24h", ...}]}}
        """
        params: dict[str, Any] = {"category": "spot"}
        if symbol:
            params["symbol"] = symbol
        return await self._get("/v5/market/tickers", params)

    async def instruments_info(self, symbol: str | None = None) -> dict[str, Any]:
        """GET /v5/market/instruments-info?category=spot[&symbol=...]

        Response includes lotSizeFilter: {minOrderQty, maxOrderQty, qtyStep,
        minNotionalValue}.
        """
        params: dict[str, Any] = {"category": "spot"}
        if symbol:
            params["symbol"] = symbol
        return await self._get("/v5/market/instruments-info", params)
