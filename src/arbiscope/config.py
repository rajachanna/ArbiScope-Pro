"""Explicit allowlists and safe demo defaults for external read-only sources."""
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
import os

EXCHANGES = frozenset({"binance", "bybit", "okx", "kraken"})
SPOT_SYMBOLS = frozenset({"BTC/USDT", "ETH/USDT", "SOL/USDT"})
DEX_CHAINS = frozenset({"ethereum", "solana", "base", "arbitrum"})


@dataclass(frozen=True)
class Settings:
    live_reads: bool = False
    db_path: Path = Path("./data/arbiscope.sqlite")
    market_symbol: str = "BTC/USDT"
    base_quantity: Decimal = Decimal("0.1")
    exchanges: tuple[str, ...] = ("binance", "okx", "bybit")
    refresh_seconds: int = 30
    max_book_age_seconds: int = 20
    taker_fee_bps: Decimal = Decimal("10")  # illustrative, NOT exchange-specific
    transfer_cost_usdt: Decimal = Decimal("0")  # not a transfer feasibility check

    @classmethod
    def from_env(cls) -> "Settings":
        get = os.environ.get
        config = cls(
            live_reads=get("AS_ENABLE_LIVE_READS", "NO") == "YES",
            db_path=Path(get("AS_DB_PATH", "./data/arbiscope.sqlite")),
            market_symbol=get("AS_MARKET_SYMBOL", "BTC/USDT").upper(),
            base_quantity=Decimal(get("AS_TRADE_BASE_QTY", "0.1")),
            exchanges=tuple(x.strip().lower() for x in get("AS_EXCHANGES", "binance,okx,bybit").split(",") if x.strip()),
            refresh_seconds=int(get("AS_SCAN_INTERVAL_SECONDS", "30")),
            max_book_age_seconds=int(get("AS_MAX_BOOK_AGE_SECONDS", "20")),
            taker_fee_bps=Decimal(get("AS_TAKER_FEE_BPS", "10")),
            transfer_cost_usdt=Decimal(get("AS_TRANSFER_COST_USDT", "0")),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.market_symbol not in SPOT_SYMBOLS:
            raise ValueError(f"Only verified same-quote spot symbols are allowed: {', '.join(sorted(SPOT_SYMBOLS))}")
        if len(self.exchanges) < 2 or len(set(self.exchanges)) != len(self.exchanges) or not set(self.exchanges) <= EXCHANGES:
            raise ValueError("Choose two or more distinct supported spot exchanges.")
        numbers = (self.base_quantity, self.taker_fee_bps, self.transfer_cost_usdt)
        if any(not x.is_finite() for x in numbers) or self.base_quantity <= 0:
            raise ValueError("Quantity and money settings must be finite; quantity must be >0.")
        if self.taker_fee_bps < 0 or self.taker_fee_bps > 1000 or self.transfer_cost_usdt < 0:
            raise ValueError("Fees must be non-negative and within realistic bounds.")
        if not (10 <= self.refresh_seconds <= 3600) or not (1 <= self.max_book_age_seconds <= 120):
            raise ValueError("Refresh interval or maximum book age out of safe range.")
