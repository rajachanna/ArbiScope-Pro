from decimal import Decimal
from datetime import datetime, timezone
from fastapi.testclient import TestClient
import pytest

from arbiscope.api import create_app
from arbiscope.config import Settings
from arbiscope.service import Scanner
from arbiscope.storage import ScanJournal


@pytest.fixture
def client(tmp_path):
    settings = Settings(db_path=tmp_path / 'test.sqlite', exchanges=('binance','okx','bybit'))
    return TestClient(create_app(settings))


def test_health_is_non_trading(client):
    data=client.get('/health').json()
    assert data['execution']=='DISABLED'
    assert data['source_mode']=='SYNTHETIC_DEMO'


def test_scan_and_history(client):
    response=client.get('/api/scan')
    assert response.status_code == 200
    data=response.json()
    assert data['source_mode']=='SYNTHETIC_DEMO'
    assert data['opportunities']
    assert all(x['classification']=='INDICATIVE_ONLY_NOT_EXECUTABLE' for x in data['opportunities'])
    history=client.get('/api/history').json()['history']
    assert len(history)==1
    assert history[0]['mode']=='DEMO'
    second=client.get('/api/scan').json()
    assert second['cached'] is True
    assert len(client.get('/api/history').json()['history'])==1


def test_dex_disabled_by_default(client):
    assert client.get('/api/dex/pools', params={'chain':'solana','token_address':'A'*32}).status_code==403


def test_html_dashboard_available(client):
    resp=client.get('/')
    assert resp.status_code==200
    assert 'ArbiScope Pro' in resp.text
    assert 'NO EXECUTION' in resp.text


def test_demo_rejects_invalid_config():
    with pytest.raises(ValueError):
        Settings(exchanges=('okx','okx')).validate()
    with pytest.raises(ValueError):
        Settings(market_symbol='BTC/USD').validate()
    with pytest.raises(ValueError):
        Settings(base_quantity=Decimal('NaN')).validate()


def test_cooldown_without_network_calls(tmp_path):
    class CountingProvider:
        def __init__(self): self.count = 0
        def fetch(self, venue, symbol):
            self.count+=1
            return Scanner(Settings()).demo_books()[0]
    # Scanner lock & cached history are exercised in offline mode, no network allowed.
    settings=Settings(db_path=tmp_path/'scan.sqlite',refresh_seconds=60,live_reads=False)
    scanner=Scanner(settings)
    a=scanner.run(); b=scanner.run()
    assert not a['cached'] and b['cached']
    assert len(scanner.history())==1


def test_public_mode_provider_errors_are_not_secrets(tmp_path):
    class Failing:
        def fetch(self, venue,symbol):
            raise RuntimeError('PRIVATE_KEY=do-not-log')
    s=Settings(db_path=tmp_path/'fail.sqlite',live_reads=True)
    result=Scanner(s,provider=Failing()).run()
    assert result['book_count']==0
    assert len(result['provider_errors'])==len(s.exchanges)
    assert 'PRIVATE_KEY' not in str(result)


def test_dex_live_api_is_read_only(tmp_path):
    class MockDex:
        def fetch(self, chain, token_address):
            return {'chain':chain,'token_address':token_address,'pools':[],'warning':'indicative only'}
    s=Settings(db_path=tmp_path/'dex.sqlite',live_reads=True)
    api=TestClient(create_app(s,dex_provider=MockDex()))
    resp=api.get('/api/dex/pools',params={'chain':'solana','token_address':'A'*32})
    assert resp.status_code==200
    assert resp.json()['pools']==[]


def test_journal_bounded(tmp_path):
    journal=ScanJournal(tmp_path/'journal.sqlite')
    for i in range(72): journal.record('DEMO',{'i':i})
    saved=journal.recent(100)
    assert len(saved)==60
    assert saved[0]['payload']['i']==71
