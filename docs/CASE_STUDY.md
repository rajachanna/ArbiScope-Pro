# ArbiScope Pro — Engineering Case Study

**Author:** Raja Channa · NextGen Tech Solutions  
**Release:** v0.1 read-only research prototype, November 2026

## Problem

A trader sees BTC priced lower on Exchange A than on Exchange B. Does that mean there is a profitable arbitrage? **No**: tickers can be stale, the order books may not have enough depth, fees can consume the difference, and buying and selling may not happen simultaneously. The target asset might not be transferable at all.

The goal of ArbiScope Pro is to demonstrate a more responsible engineering workflow: **ingest → validate → evaluate liquidity → model explicit costs → communicate uncertainty**.

## Technical approach

1. Default to synthetic fixtures so researchers can reproduce calculations without API keys.
2. When explicitly opted in, use CCXT public spot order-book endpoints with no private or order-creation API calls.
3. Normalize every bid/ask level to decimal arithmetic. Reject invalid numbers, crossed books, insufficient size and stale responses. Source timestamp (if present) is checked independently of receipt time.
4. Evaluate both buy/sell venue directions at an explicit base-asset quantity. Walk available asks to calculate the **total hypothetical buy cost**, walk bids for the **total hypothetical sale proceeds**. Deduct a configurable fee on each leg and an optional estimated transfer fee.
5. Label output **theoretical, not executable**. Sort directional comparisons by theoretical net quote value; do not call a positive result guaranteed profit.
6. Store up to 60 recent scan payloads in local SQLite and serve a responsive read-only dashboard.
7. Provide an independent DEX Screener research adapter that returns indicative USD prices and reported liquidity of qualifying USDT/USDC pools, without pretending it quotes a live swap.

## Critical limitations

- CCXT source timestamps may be missing; local receipt timestamp cannot verify when the exchange actually built its book.
- Public books can be unavailable or stale. Different exchanges have different network availability, fee schedules, matching rules and quote conditions.
- USDT quotes cannot be blindly treated as USD cash. The software does not prove custody, capital, withdrawal network, order acceptance or transfer feasibility.
- Liquidity from DEX Screener is **reported/indicative** and not a size-specific swap execution estimate. There is no routing, slippage simulation, gas, MEV, transfer, contract tax or token audit.
- Default fee of 10 basis points per leg is **illustrative only**; users must not interpret it as an exchange-verified schedule. Even correct fees would not make this an executable strategy.
- Neither real trading nor exchange credentials are used. **There are no live profits or backtest performance results.**

## Portfolio acceptance criteria

A reviewer can check that:

- Two-level book walks produce the correct volume-weighted quote amount.
- An insufficient-depth market yields a warning rather than a misleading theoretical fill.
- An invalid, crossed, stale or wrong-quote market is rejected.
- DEX pool data is clearly labeled non-executable and cannot contain an arbitrary URL from a user.
- The application can be launched with completely synthetic data and its scan persisted.
- Public data reads are disabled by default; no order-creation function is implemented.

## Suggested paid client applications

Custom market-data ingestion, multi-venue liquidity monitoring, alerting dashboards, order-book analytics, read-only broker connectivity preflights, risk monitoring and auditable execution-system design. Any future trading functionality would require its own security and market-integrity evaluation.

**Contact:** https://nextgentechdev.com
