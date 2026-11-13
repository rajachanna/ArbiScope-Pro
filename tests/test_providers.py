import io
import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

from arbiscope.providers import CCXTPublicBooks, DexScreenerPools, ProviderError


class HTTPResponse(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *args): self.close()


def test_cex_public_order_book_spot_only():
    exchange = SimpleNamespace(
        markets={'BTC/USDT': {'spot': True, 'active': True}},
        has={'fetchOrderBook': True},
        load_markets=Mock(),
        fetch_order_book=Mock(return_value={'bids': [[100, 1]], 'asks': [[101, 1]], 'timestamp': None}),
        close=Mock(),
    )
    provider = CCXTPublicBooks(exchange_factory=lambda name: exchange)
    result = provider.fetch('okx', 'BTC/USDT')
    assert result.venue == 'okx'
    exchange.load_markets.assert_called_once()
    exchange.fetch_order_book.assert_called_once_with('BTC/USDT', 20)
    exchange.close.assert_called_once()
    assert not hasattr(exchange, 'create_order')


def test_refuse_futures():
    exchange = SimpleNamespace(markets={'BTC/USDT': {'spot': False}}, has={'fetchOrderBook': True},
        load_markets=Mock(), fetch_order_book=Mock(), close=Mock())
    with pytest.raises(ProviderError, match='spot'):
        CCXTPublicBooks(exchange_factory=lambda name: exchange).fetch('okx', 'BTC/USDT')
    exchange.fetch_order_book.assert_not_called()
    exchange.close.assert_called_once()


def test_exchange_allowlist_rejects_untrusted_name():
    with pytest.raises(ProviderError):
        CCXTPublicBooks(exchange_factory=lambda name: None).fetch('malicious', 'BTC/USDT')


def test_dex_filters_token_quote_and_liquidity():
    address='A' * 32
    rows=[
        {'chainId':'solana','dexId':'raydium','pairAddress':'b'*32,
         'baseToken':{'address':address,'symbol':'SOL'},'quoteToken':{'symbol':'USDC'},
         'priceUsd':'154.42','liquidity':{'usd':25000}},
        {'chainId':'solana','dexId':'fake','pairAddress':'c'*32,
         'baseToken':{'address':address,'symbol':'SOL'},'quoteToken':{'symbol':'USDC'},
         'priceUsd':'155.00','liquidity':{'usd':100}},
        {'chainId':'base','dexId':'wrongchain','baseToken':{'address':address,'symbol':'SOL'},
         'quoteToken':{'symbol':'USDT'},'priceUsd':'154','liquidity':{'usd':200000}}
    ]
    calls=[]
    def opener(req, **kwargs):
        calls.append((req, kwargs)); return HTTPResponse(json.dumps(rows).encode())
    result=DexScreenerPools(opener=opener).fetch('solana',address)
    assert len(result['pools']) == 1
    assert result['pools'][0]['dex'] == 'raydium'
    assert result['pools'][0]['classification'] == 'DEX_INDICATIVE_POOL_METADATA_NOT_SWAP_QUOTE'
    assert calls[0][0].get_method() == 'GET'
    assert calls[0][0].full_url == f'https://api.dexscreener.com/token-pairs/v1/solana/{address}'


@pytest.mark.parametrize('chain,address', [('evil.com','A'*32),('solana','/etc/passwd'),('solana','short')])
def test_dex_rejects_bad_chain_or_address(chain,address):
    with pytest.raises(ProviderError):
        DexScreenerPools(opener=lambda *_args,**_kwargs: None).fetch(chain,address)


def test_dex_rejects_unexpected_json_shape():
    with pytest.raises(ProviderError, match='Unexpected'):
        DexScreenerPools(opener=lambda *_a,**_k:HTTPResponse(b'{}')).fetch('solana','A'*32)
