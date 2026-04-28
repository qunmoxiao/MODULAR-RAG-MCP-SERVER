"""Unit tests for QA->wiki pipeline components."""

from __future__ import annotations

from src.knowledge.candidate_fact_extractor import CandidateFactExtractor
from src.knowledge.fact_promoter import FactPromoter
from src.knowledge.markdown_exporter import MarkdownExporter


def test_candidate_fact_extractor_extracts_minimal_fact() -> None:
    extractor = CandidateFactExtractor()
    facts = extractor.extract(
        query="什么是RRF？",
        answer="RRF 是一种融合排序策略，常用于混合检索结果融合。",
        citations=["chunk-1"],
    )
    assert len(facts) == 1
    assert facts[0]["statement"].startswith("RRF")
    assert facts[0]["confidence"] >= 0.5


def test_fact_promoter_keeps_low_confidence_in_candidates() -> None:
    promoter = FactPromoter(promote_threshold=0.8, candidate_threshold=0.55)
    decision = promoter.classify(
        {"statement": "RRF 常用于融合排序", "confidence": 0.6}
    )
    assert decision == "candidate"


def test_markdown_exporter_writes_fact_pages(tmp_path) -> None:
    exporter = MarkdownExporter(base_dir=str(tmp_path))
    exporter.export_facts(
        [
            {
                "statement": "RRF 是一种融合排序策略",
                "confidence": 0.9,
                "citations": ["chunk-1"],
            }
        ]
    )
    content = (tmp_path / "facts.md").read_text(encoding="utf-8")
    assert "RRF 是一种融合排序策略" in content
