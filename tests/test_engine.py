from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from arbiscope.engine import InsufficientDepth, compare, depth_cost, normalize_book, scan_books, fresh

NOW = datetime(2026, 11, 13, tzinfo=timezone.utc)


def book(venue, bids=None, asks=None, when=NOW, timestamp=None, symbol='BTC/USDT'):
    return normalize_book(venue, symbol, {
        'bids': bids or [['104', '2']], 'asks': asks or [['105', '2']],
        'timestamp': timestamp,
    }, observed_at=when)


def test_depth_walk_buy():
    levels = ((Decimal('10'), Decimal('1')), (Decimal('11'), Decimal('2')))
    assert depth_cost(levels, Decimal('2'), buy=True) == Decimal('21')


def test_depth_walk_sell_highest_first():
    levels = ((Decimal('10'), Decimal('1')), (Decimal('11'), Decimal('2')))
    assert depth_cost(levels, Decimal('2'), buy=False) == Decimal('22')


def test_insufficient_depth():
    with pytest.raises(InsufficientDepth):
        depth_cost(((Decimal('10'), Decimal('1')),), Decimal('2'), buy=True)


def test_fee_adjusted_calculation():
    buy = book('binance', bids=[['98', '5']], asks=[['100', '5']])
    sell = book('okx', bids=[['103', '5']], asks=[['104', '5']])
    r = compare(buy, sell, Decimal('1'), Decimal('10'), Decimal('0.5'))
    assert Decimal(r['buy_cost_usdt']) == Decimal('100')
    assert Decimal(r['sell_proceeds_usdt']) == Decimal('103')
    assert Decimal(r['assumed_taker_fees_usdt']) == Decimal('0.203')
    assert Decimal(r['theoretical_net_usdt']) == Decimal('2.297')
    assert r['classification'] == 'INDICATIVE_ONLY_NOT_EXECUTABLE'


def test_cannot_compare_same_venue():
    with pytest.raises(ValueError):
        compare(book('binance'), book('binance'), Decimal('1'), Decimal('10'), Decimal('0'))


def test_cannot_compare_different_quote_market():
    with pytest.raises(ValueError):
        compare(book('binance', symbol='BTC/USDT'), book('okx', symbol='BTC/USD'), Decimal('1'), Decimal('10'), Decimal('0'))


def test_crossed_book_rejected():
    with pytest.raises(ValueError):
        book('binance', bids=[['101', '1']], asks=[['100', '1']])


@pytest.mark.parametrize('bad', ['NaN', '-1', 'Infinity', '0', 'bad'])
def test_invalid_levels_rejected(bad):
    with pytest.raises(ValueError):
        book('binance', asks=[[bad, '1']])


def test_stale_book_excluded():
    stale = book('binance', when=NOW - timedelta(seconds=30))
    good = book('okx')
    result = scan_books([stale, good], quantity=Decimal('1'), fee_bps=Decimal('10'),
                        transfer_usdt=Decimal('0'), max_age_seconds=20, now=NOW)
    assert result['book_count'] == 1
    assert not result['opportunities']
    assert result['warnings'][0]['reason'] == 'STALE_OR_FUTURE_BOOK'


def test_exchange_timestamp_absent_does_not_claim_verified():
    result = compare(book('binance'), book('okx'), Decimal('1'), Decimal('10'), Decimal('0'))
    assert result['quote_timestamp_verified'] is False


def test_exchange_source_time_stale():
    old_ms = int((NOW - timedelta(minutes=1)).timestamp() * 1000)
    item = book('binance', timestamp=old_ms)
    assert not fresh(item, NOW, 20)


def test_no_depth_opportunity_excluded():
    result = scan_books([book('binance'), book('okx')], quantity=Decimal('4'),
                        fee_bps=Decimal('10'), transfer_usdt=Decimal('0'), max_age_seconds=20, now=NOW)
    assert not result['opportunities']
    assert result['warnings']


def test_duplicates_venue_rejected():
    with pytest.raises(ValueError):
        scan_books([book('okx'), book('okx')], quantity=Decimal('1'), fee_bps=Decimal('10'),
                   transfer_usdt=Decimal('0'), max_age_seconds=20, now=NOW)
