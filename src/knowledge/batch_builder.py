"""Periodic builder for promoted facts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from src.knowledge.fact_promoter import FactPromoter
from src.knowledge.markdown_exporter import MarkdownExporter


@dataclass
class BatchBuildResult:
    promoted_count: int
    candidate_count: int


class BatchBuilder:
    """Run promotion and optional markdown export for fact batches."""

    def __init__(self, promoter: FactPromoter, exporter: MarkdownExporter | None = None) -> None:
        self.promoter = promoter
        self.exporter = exporter

    def run(self, facts: List[Dict[str, Any]]) -> BatchBuildResult:
        promoted, candidates = self.promoter.split(facts)
        if self.exporter is not None and promoted:
            self.exporter.export_facts(promoted)
        return BatchBuildResult(
            promoted_count=len(promoted),
            candidate_count=len(candidates),
        )
