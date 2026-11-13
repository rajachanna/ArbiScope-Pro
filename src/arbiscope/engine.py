"""Deterministic, Decimal-based read-only order-book spread RESEARCH.

Theoretical cross-venue figures are NOT executable arbitrage or realized profit.
Order-book depth and illustrative taker fees are modeled, but execution risk,
funding, deposits/withdrawals, transfer delays, basis and regulatory access are not.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from itertools import permutations


class InsufficientDepth(ValueError):
    """Insufficient book depth to execute the *hypothetical* base quantity."""


def decimal(value) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid decimal price or quantity") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError("Order-book prices and sizes must be positive and finite")
    return parsed


@dataclass(frozen=True)
class Book:
    venue: str
    symbol: str
    bids: tuple[tuple[Decimal, Decimal], ...]
    asks: tuple[tuple[Decimal, Decimal], ...]
    received_at: datetime
    source_at: datetime | None = None

    def validate(self) -> None:
        if self.received_at.utcoffset() is None or (self.source_at is not None and self.source_at.utcoffset() is None):
            raise ValueError("All book timestamps must carry an offset")
        if not self.bids or not self.asks:
            raise ValueError("Order book missing bids or asks")
        for side in (self.bids, self.asks):
            for price, amount in side:
                decimal(price)
                decimal(amount)
        if max(price for price, _ in self.bids) >= min(price for price, _ in self.asks):
            raise ValueError("Crossed/locked venue book cannot be used")


def normalize_book(venue: str, symbol: str, payload: dict, *, observed_at: datetime | None = None) -> Book:
    if not isinstance(payload, dict):
        raise ValueError("Order book must be an object")
    ts_ms = payload.get("timestamp")
    source_at = datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc) if ts_ms is not None else None

    def side_levels(raw):
        if not isinstance(raw, list):
            raise ValueError("Order-book side must be a list")
        items = []
        for entry in raw:
            if not isinstance(entry, (tuple, list)) or len(entry) < 2:
                raise ValueError("Malformed order-book level")
            items.append((decimal(entry[0]), decimal(entry[1])))
        return tuple(items)

    book = Book(
        venue=venue, symbol=symbol,
        bids=side_levels(payload.get("bids")), asks=side_levels(payload.get("asks")),
        received_at=observed_at or datetime.now(timezone.utc), source_at=source_at,
    )
    book.validate()
    return book


def fresh(book: Book, now: datetime, max_age_seconds: int) -> bool:
    arrival_age = (now - book.received_at).total_seconds()
    if not (0 <= arrival_age <= max_age_seconds):
        return False
    if book.source_at is not None:
        source_age = (now - book.source_at).total_seconds()
        if not (0 <= source_age <= max_age_seconds):
            return False
    return True


def depth_cost(levels: tuple[tuple[Decimal, Decimal], ...], quantity: Decimal, buy: bool) -> Decimal:
    """Quote amount for a fixed base quantity, walking the order book."""
    remaining = decimal(quantity)
    total = Decimal("0")
    ordered = sorted(levels, key=lambda row: row[0], reverse=not buy)
    for price, available in ordered:
        take = min(available, remaining)
        total += price * take
        remaining -= take
        if remaining == 0:
            return total
    raise InsufficientDepth("Insufficient hypothetical market depth for the requested size")


def compare(buy: Book, sell: Book, quantity: Decimal, fee_bps: Decimal, transfer_usdt: Decimal) -> dict:
    if buy.venue == sell.venue or buy.symbol != sell.symbol:
        raise ValueError("Different venues and identical exact market symbols required")
    cost = depth_cost(buy.asks, quantity, buy=True)
    proceeds = depth_cost(sell.bids, quantity, buy=False)
    fees = (cost + proceeds) * fee_bps / Decimal("10000")
    gross = proceeds - cost
    net = gross - fees - transfer_usdt
    return {
        "symbol": buy.symbol, "buy_venue": buy.venue, "sell_venue": sell.venue,
        "base_quantity": str(quantity), "buy_cost_usdt": str(cost),
        "sell_proceeds_usdt": str(proceeds), "gross_spread_usdt": str(gross),
        "assumed_taker_fees_usdt": str(fees), "assumed_transfer_cost_usdt": str(transfer_usdt),
        "theoretical_net_usdt": str(net),
        "theoretical_roi_pct": str(net / cost * 100),
        "quote_timestamp_verified": buy.source_at is not None and sell.source_at is not None,
        "classification": "INDICATIVE_ONLY_NOT_EXECUTABLE",
    }


def scan_books(books: list[Book], *, quantity: Decimal, fee_bps: Decimal,
               transfer_usdt: Decimal, max_age_seconds: int, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    errors = []
    eligible = []
    for book in books:
        try:
            book.validate()
            if not fresh(book, now, max_age_seconds):
                errors.append({"venue": book.venue, "reason": "STALE_OR_FUTURE_BOOK"})
                continue
            eligible.append(book)
        except ValueError:
            errors.append({"venue": book.venue, "reason": "INVALID_ORDER_BOOK"})
    if len({b.venue for b in eligible}) != len(eligible):
        raise ValueError("At most one book per venue is supported")
    results = []
    for buy, sell in permutations(eligible, 2):
        try:
            results.append(compare(buy, sell, quantity, fee_bps, transfer_usdt))
        except (InsufficientDepth, ValueError):
            errors.append({"venue": f"{buy.venue}->{sell.venue}", "reason": "INSUFFICIENT_DEPTH_OR_MARKET_MISMATCH"})
    results.sort(key=lambda x: Decimal(x["theoretical_net_usdt"]), reverse=True)
    return {
        "mode": "RESEARCH_ONLY_NO_ORDERS",
        "scanned_at": now.isoformat(), "book_count": len(eligible),
        "opportunities": results, "warnings": errors,
        "notes": [
            "Estimated depth-based spread; no orders were placed.",
            "Fees are illustrative configured assumptions, not verified exchange fees.",
            "No guarantee of inventory, transferable assets, settlement speed, gas, slippage, or available execution.",
            "USDT is not guaranteed equal to USD; venues may use different conditions.",
        ],
    }
