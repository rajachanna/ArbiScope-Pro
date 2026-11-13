"""Dashboard and read-only research API; no order routing endpoints exist."""
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from . import __version__
from .config import Settings
from .providers import DexScreenerPools, ProviderError
from .service import Scanner


def create_app(settings: Settings | None = None, scanner=None, dex_provider=None) -> FastAPI:
    config = settings or Settings.from_env()
    config.validate()
    app = FastAPI(
        title="ArbiScope Pro | Arbitrage Research (No Trading)",
        version=__version__,
        description="Fee-aware depth-based cross-exchange spread research and DEX indicative pool data. No real order execution.",
    )
    service = scanner or Scanner(config)
    dex = dex_provider or DexScreenerPools()

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(Path(__file__).parent / "static" / "index.html")

    @app.get("/health")
    def health():
        return {"ok": True, "version": __version__, "source_mode": "PUBLIC_READ_ONLY" if config.live_reads else "SYNTHETIC_DEMO", "execution": "DISABLED"}

    @app.get("/api/scan")
    def scan():
        return service.run()

    @app.get("/api/history")
    def history():
        return {"history": service.history()}

    @app.get("/api/dex/pools")
    def dex_pools(chain: str, token_address: str):
        if not config.live_reads:
            raise HTTPException(403, "DEX live public reads are disabled in offline demo mode")
        try:
            return dex.fetch(chain, token_address)
        except ProviderError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app


app = create_app()
