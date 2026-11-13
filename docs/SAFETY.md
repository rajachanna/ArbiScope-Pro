# Safety, security and accuracy boundaries

ArbiScope Pro is an informational, **read-only market-data research tool**.

- No orders can be placed: the source contains no exchange API credentials, private account calls, wallet access, keys or transaction submission.
- No financial returns are guaranteed or implied. Any positive 'theoretical_net_usdt' is merely a deterministic calculation from a time-specific order-book snapshot (or synthetic fixtures).
- Data may be missing, outdated, inaccurate or inaccessible due to provider API limits and regional restrictions.
- Fees are **manual assumptions** rather than account-verified taker fees; they exclude venue-specific discounts, actual funding, transfer networks and exchange quote currency settlement.
- We do **not** establish cross-venue token identity, deposit/withdraw compatibility, chain or wrapped-asset equivalence. Do not treat same ticker text as proof of identical transferable assets.
- The DEX Screener API returns pool metadata and indicative spot prices, not executable route quotes. Quote tokens, reserves, on-chain taxes, gas fees, slippage and MEV can be materially different during a real swap.
- Public provider requests are made only to an exchange allowlist or the fixed HTTPS domain `api.dexscreener.com`. Chain and token address inputs are validated against explicit allowlists.
- An explicit `AS_ENABLE_LIVE_READS=YES` environment variable is required to enable public internet reads. No secret values are needed or expected.
- The included Docker setup binds to localhost. Add authentication, rate limiting, monitoring, hardening and TLS before hosting the API publicly.
- Scan results are kept in local SQLite for debugging; do not use them as verified financial or tax records.

The demo dataset is intentionally synthetic and for visualization only. Do not advertise demo spreads as current market opportunities.
