"""Safe, synchronous, cooldown-limited scan orchestration."""
from datetime import datetime, timezone
from decimal import Decimal
from threading import Lock
import time

from .config import Settings
from .engine import Book, normalize_book, scan_books
from .providers import CCXTPublicBooks
from .storage import ScanJournal


class Scanner:
    def __init__(self, settings: Settings, provider=None, journal=None, clock=None):
        settings.validate()
        self.settings = settings
        self.provider = provider or CCXTPublicBooks()
        self.journal = journal or ScanJournal(settings.db_path)
        self.clock = clock or time.monotonic
        self.lock = Lock()
        self._last_tick: float | None = None
        self._latest: dict | None = None

    def demo_books(self) -> list[Book]:
        # Intentionally synthetic, NOT a market snapshot.
        # Two-level books illustrate depth walk and a theoretical spread.
        now = datetime.now(timezone.utc)
        fixtures = {
            "binance": {"bids": [["64970", "0.05"], ["64950", "1.2"]], "asks": [["65000", "0.03"], ["65010", "1.2"]]},
            "okx": {"bids": [["65110", "0.04"], ["65095", "1.2"]], "asks": [["65130", "0.1"], ["65135", "1.2"]]},
            "bybit": {"bids": [["65075", "0.03"], ["65055", "1.2"]], "asks": [["65100", "0.1"], ["65110", "1.2"]]},
            "kraken": {"bids": [["65030", "0.08"], ["65020", "1.2"]], "asks": [["65060", "0.05"], ["65070", "1.2"]]},
        }
        # Fixture values are BTC-sized; ETH/SOL demo labels must not inherit BTC-sized prices.
        multiplier = {"BTC/USDT": Decimal("1"), "ETH/USDT": Decimal("0.05"), "SOL/USDT": Decimal("0.002")} [self.settings.market_symbol]
        result = []
        for venue in self.settings.exchanges:
            base = fixtures[venue]
            payload = {side: [[str(Decimal(p) * multiplier), amount] for p, amount in base[side]] for side in ("bids", "asks")}
            result.append(normalize_book(venue, self.settings.market_symbol, payload, observed_at=now))
        return result

    def run(self) -> dict:
        with self.lock:
            tick = self.clock()
            if self._latest is not None and self._last_tick is not None and tick - self._last_tick < self.settings.refresh_seconds:
                return {**self._latest, "cached": True}
            errors = []
            books = []
            if self.settings.live_reads:
                for venue in self.settings.exchanges:
                    try:
                        books.append(self.provider.fetch(venue, self.settings.market_symbol))
                    except Exception:
                        errors.append({"venue": venue, "reason": "PROVIDER_READ_FAILED"})
            else:
                books = self.demo_books()
            result = scan_books(
                books, quantity=self.settings.base_quantity, fee_bps=self.settings.taker_fee_bps,
                transfer_usdt=self.settings.transfer_cost_usdt,
                max_age_seconds=self.settings.max_book_age_seconds,
            )
            result["source_mode"] = "PUBLIC_READ_ONLY" if self.settings.live_reads else "SYNTHETIC_DEMO"
            result["market_symbol"] = self.settings.market_symbol
            result["requested_base_quantity"] = str(self.settings.base_quantity)
            result["fee_assumption_bps_each_leg"] = str(self.settings.taker_fee_bps)
            result["provider_errors"] = errors
            result["cached"] = False
            self.journal.record("PUBLIC_READ_ONLY" if self.settings.live_reads else "DEMO", result)
            self._latest, self._last_tick = result, tick
            return result

    def history(self):
        return self.journal.recent()
