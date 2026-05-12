"""Peaberry quantitative research toolkit."""

from peaberry.backtesting.engine import BacktestEngine, BacktestResult
from peaberry.domain.fundamentals import FinancialStatement, FundamentalRow
from peaberry.domain.market import Bar, Symbol
from peaberry.domain.portfolio import Portfolio
from peaberry.domain.signal import TargetAllocation
from peaberry.fundamentals.coverage import FundamentalCoveragePlanner
from peaberry.fundamentals.display import FundamentalDisplayMapper
from peaberry.fundamentals.factory import build_fundamentals_source
from peaberry.fundamentals.pipeline import FundamentalDataPipeline
from peaberry.fundamentals.resolver import FundamentalDataResolver
from peaberry.fundamentals.ui import FundamentalUiPresenter

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "Bar",
    "FinancialStatement",
    "FundamentalCoveragePlanner",
    "FundamentalDataPipeline",
    "FundamentalDataResolver",
    "FundamentalDisplayMapper",
    "FundamentalUiPresenter",
    "FundamentalRow",
    "Portfolio",
    "Symbol",
    "TargetAllocation",
    "build_fundamentals_source",
]
