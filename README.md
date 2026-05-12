# peaberry

`peaberry` is a Python toolkit scaffold for professional quantitative research
and backtesting.  The design separates alpha generation, market data, risk,
execution, and portfolio accounting so each layer can evolve independently.

## Architecture

```text
src/peaberry/
  domain/       Immutable market data, signals, trades, and portfolio state
  data/         Market data source adapters
  fundamentals/ Fundamental data source composition and gap resolution
  strategies/   Alpha models that emit target allocations
  risk/         Pre-trade portfolio and exposure controls
  execution/    Backtest/live execution model boundary
  backtesting/  Event-driven orchestration and result objects
  ports.py      Protocols that define subsystem contracts
```

Key design choices:

- Strategies emit `TargetAllocation` objects instead of orders, keeping alpha
  logic separate from sizing, fills, and fee assumptions.
- `MarketDataSource`, `Strategy`, `RiskModel`, and `ExecutionModel` are defined
  as protocols to make vendor adapters and live trading integrations swappable.
- Portfolio accounting uses explicit mark-to-market prices and `Decimal` values
  to avoid hidden float drift in core financial state.
- The backtesting engine coordinates modules through application ports instead
  of coupling directly to concrete strategy or data implementations.
- Fundamental rows keep source provenance and expose explicit `missing_fields`
  so UI tables can distinguish unavailable data from derived estimates.

## Fundamental gap-filling plan

For company financial tables, missing cells should be filled from prioritized
sources before the UI renders:

1. **Regulatory filings**: DART for Korean issuers and SEC Company Facts for
   US issuers provide audited revenue, operating income, net income, equity,
   diluted shares, and dividends when available.
2. **Company IR**: earnings releases and annual reports fill filing taxonomy
   gaps, especially segment totals or locally reported line items.
3. **Market data**: latest price or market cap is required to compute PER/PBR
   and dividend yield.
4. **Analyst or internal estimates**: future periods such as `2027.12(E)` are
   accepted as estimates and marked with reduced confidence.
5. **Derived metrics**: EPS, BPS, ROE, PER, PBR, and dividend yield are computed
   from sourced facts instead of being stored as independent truths.

The `fundamentals` package implements this as:

- `FundamentalsSource`: adapter contract for DART, SEC, IR imports, market data,
  or estimate feeds.
- `CompositeFundamentalsSource`: priority merge that preserves high-quality
  values and fills blanks from lower-priority sources.
- `FundamentalDataResolver`: produces display-ready `FundamentalRow` objects
  with values, source provenance, estimate flags, and remaining gaps.
- `FundamentalCoveragePlanner`: converts unresolved cells into acquisition
  requests such as "fetch DART/SEC net income and diluted shares" or "fetch
  KRX/Nasdaq period-end price or market cap".

Valuation cells are resolved per fiscal period.  If a row has EPS/BPS but PER or
PBR remains empty, the planner requests a period-specific market reference.  If
the quote is unavailable, `MarketReference.market_cap` plus diluted shares can be
used to derive a comparable valuation price.  Market references are currency
checked before valuation metrics are calculated.

## Quick start

```bash
PYTHONPATH=src python3 -m unittest discover
```

Minimal example:

```python
from datetime import datetime, timezone
from decimal import Decimal

from peaberry.backtesting import BacktestEngine
from peaberry.data import InMemoryMarketDataSource
from peaberry.domain.market import Bar, Symbol
from peaberry.execution import SimulatedExecutionModel
from peaberry.risk import LimitRiskModel, RiskLimits
from peaberry.strategies import MovingAverageCrossStrategy

symbol = Symbol("AAPL")
bars = [
    Bar(symbol, datetime(2026, 1, 1, tzinfo=timezone.utc), 10, 10, 10, 10),
    Bar(symbol, datetime(2026, 1, 2, tzinfo=timezone.utc), 11, 11, 11, 11),
    Bar(symbol, datetime(2026, 1, 3, tzinfo=timezone.utc), 12, 12, 12, 12),
]

engine = BacktestEngine(
    data_source=InMemoryMarketDataSource(bars),
    strategy=MovingAverageCrossStrategy(2, 3, Decimal("0.5")),
    risk_model=LimitRiskModel(RiskLimits(max_abs_weight=Decimal("0.5"))),
    execution_model=SimulatedExecutionModel(),
)

result = engine.run([symbol], bars[0].timestamp, bars[-1].timestamp)
print(result.final_equity)
```
