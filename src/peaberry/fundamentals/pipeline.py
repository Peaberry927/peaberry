"""End-to-end fundamental data acquisition and resolution pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from peaberry.domain.fundamentals import FundamentalRow
from peaberry.domain.market import Symbol
from peaberry.fundamentals.coverage import (
    FundamentalAcquisitionRequest,
    FundamentalCoveragePlanner,
)
from peaberry.fundamentals.resolver import FundamentalDataResolver
from peaberry.fundamentals.sources import FundamentalsSource


@dataclass(frozen=True, slots=True)
class FundamentalPipelineResult:
    """Resolved rows plus remaining data acquisition work."""

    rows: tuple[FundamentalRow, ...]
    acquisition_requests: tuple[FundamentalAcquisitionRequest, ...]
    source_errors: tuple[tuple[str, str], ...] = ()

    @property
    def is_complete(self) -> bool:
        return not self.acquisition_requests


class FundamentalDataPipeline:
    """Acquire, resolve, and diagnose fundamentals in one application service."""

    def __init__(
        self,
        source: FundamentalsSource,
        coverage_planner: FundamentalCoveragePlanner | None = None,
    ) -> None:
        self.source = source
        self.resolver = FundamentalDataResolver(source)
        self.coverage_planner = coverage_planner or FundamentalCoveragePlanner()

    def run(
        self,
        symbol: Symbol,
        fiscal_periods: Sequence[str],
    ) -> FundamentalPipelineResult:
        rows = self.resolver.rows(symbol, fiscal_periods)
        return FundamentalPipelineResult(
            rows=rows,
            acquisition_requests=self.coverage_planner.plan(rows),
            source_errors=getattr(self.source, "source_errors", ()),
        )
