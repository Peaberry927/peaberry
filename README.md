# peaberry

`peaberry` is a Python toolkit scaffold for professional quantitative research
and backtesting.  The design separates alpha generation, market data, risk,
execution, and portfolio accounting so each layer can evolve independently.

## Architecture

```text
src/peaberry/
  domain/       Immutable market data, signals, trades, and portfolio state
  data/         Market data source adapters
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
