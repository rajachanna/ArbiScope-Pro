"""Public-data-only connectors; intentionally exposes no trading operations."""
from datetime import datetime, timezone
from decimal import Decimal
import json
import re
from urllib import request

from .config import DEX_CHAINS, EXCHANGES
from .engine import Book, normalize_book, decimal


class ProviderError(RuntimeError):
    """Safe, limited detail from public-data errors."""


class CCXTPublicBooks:
    """Fetch SPOT order books only; no API credentials, no private API methods."""

    def __init__(self, exchange_factory=None):
        self.exchange_factory = exchange_factory

    def fetch(self, venue: str, symbol: str, *, limit: int = 20) -> Book:
        if venue not in EXCHANGES:
            raise ProviderError("Unsupported exchange")
        if not (5 <= limit <= 50):
            raise ProviderError("Order-book depth limit must be from 5 to 50")
        if self.exchange_factory is None:
            try:
                import ccxt
            except ImportError as exc:
                raise ProviderError("Optional ccxt library missing. Install with pip install -e '.[live]'") from exc
            factory = getattr(ccxt, venue)
        else:
            factory = lambda: self.exchange_factory(venue)
        exchange = None
        try:
            exchange = factory() if self.exchange_factory else factory({"enableRateLimit": True, "timeout": 8000})
            exchange.load_markets()
            market = exchange.markets.get(symbol)
            if not market or market.get("spot") is not True or market.get("active") is False:
                raise ProviderError("Market is unavailable or is not a supported active spot market")
            if exchange.has.get("fetchOrderBook") is False:
                raise ProviderError("Public order books not supported")
            data = exchange.fetch_order_book(symbol, limit)
            # Capture local receipt after the network call. It does NOT prove original quote freshness.
            return normalize_book(venue, symbol, data, observed_at=datetime.now(timezone.utc))
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"Public order book query failed for {venue}; check network, geo-availability and provider limits") from exc
        finally:
            if exchange is not None:
                close = getattr(exchange, "close", None)
                if callable(close):
                    close()


ALLOWED_ADDRESS = re.compile(r"^[A-Za-z0-9]{20,90}$")


class DexScreenerPools:
    """DEX Screener token pair metadata. Not an executable swap quote."""

    def __init__(self, opener=None):
        self.opener = opener or request.urlopen

    def fetch(self, chain: str, address: str, *, minimum_liquidity_usd: Decimal = Decimal("10000")) -> dict:
        if chain not in DEX_CHAINS or not ALLOWED_ADDRESS.fullmatch(address):
            raise ProviderError("Unsupported chain or invalid token contract address")
        if not minimum_liquidity_usd.is_finite() or minimum_liquidity_usd < 0:
            raise ProviderError("Invalid liquidity threshold")
        url = f"https://api.dexscreener.com/token-pairs/v1/{chain}/{address}"
        req = request.Request(url, headers={"Accept": "application/json", "User-Agent": "ArbiScopePro/0.1 read-only"}, method="GET")
        try:
            with self.opener(req, timeout=8) as response:
                data = json.load(response)
        except Exception as exc:
            raise ProviderError("DEX public pool lookup failed; check network or provider limits") from exc
        if not isinstance(data, list):
            raise ProviderError("Unexpected DEX pool response")
        pools = []
        for pool in data[:100]:
            if not isinstance(pool, dict) or pool.get("chainId") != chain:
                continue
            token = pool.get("baseToken") or {}
            if str(token.get("address", "")).lower() != address.lower():
                # This must be a direct base-token quote, not an inverted pair.
                continue
            quote = pool.get("quoteToken") or {}
            if str(quote.get("symbol", "")).upper() not in {"USDT", "USDC"}:
                continue
            try:
                price_usd = decimal(pool.get("priceUsd"))
                liquidity_usd = decimal((pool.get("liquidity") or {}).get("usd"))
            except ValueError:
                continue
            if liquidity_usd < minimum_liquidity_usd:
                continue
            pools.append({
                "chain": chain,
                "dex": str(pool.get("dexId") or "unknown")[:64],
                "pair_address": str(pool.get("pairAddress") or "")[:128],
                "base_symbol": str(token.get("symbol") or "unknown")[:24],
                "quote_symbol": str(quote.get("symbol") or "unknown")[:24],
                "indicative_price_usd": str(price_usd),
                "reported_liquidity_usd": str(liquidity_usd),
                "classification": "DEX_INDICATIVE_POOL_METADATA_NOT_SWAP_QUOTE",
            })
        pools.sort(key=lambda p: Decimal(p["reported_liquidity_usd"]), reverse=True)
        return {
            "source": "DEX_SCREENER_PUBLIC",
            "chain": chain, "token_address": address,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "pools": pools[:30],
            "warning": "DEX Screener's indicative price/liquidity is not a route-specific executable quote; gas, token restrictions, MEV, taxes, chain risk and slippage are not modeled.",
        }
