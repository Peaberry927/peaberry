"""Presentation objects consumed by the fundamentals screen."""

from __future__ import annotations

from dataclasses import dataclass

from peaberry.fundamentals.display import FundamentalDisplayMapper, FundamentalDisplayRow
from peaberry.fundamentals.pipeline import FundamentalPipelineResult


@dataclass(frozen=True, slots=True)
class FundamentalScreenModel:
    """UI-ready fundamentals table data."""

    rows: tuple[FundamentalDisplayRow, ...]
    source_errors: tuple[tuple[str, str], ...]
    has_source_errors: bool


class FundamentalUiPresenter:
    """Connect pipeline output to the screen layer."""

    def __init__(self, display_mapper: FundamentalDisplayMapper | None = None) -> None:
        self.display_mapper = display_mapper or FundamentalDisplayMapper()

    def present(self, result: FundamentalPipelineResult) -> FundamentalScreenModel:
        return FundamentalScreenModel(
            rows=tuple(self.display_mapper.map_row(row) for row in result.rows),
            source_errors=result.source_errors,
            has_source_errors=bool(result.source_errors),
        )
