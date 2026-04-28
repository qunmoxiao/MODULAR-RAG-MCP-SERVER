"""Extract candidate facts from QA events."""

from __future__ import annotations

from typing import Any, Dict, List


class CandidateFactExtractor:
    """Minimal deterministic extractor for structured candidate facts."""

    def extract(self, query: str, answer: str, citations: List[str]) -> List[Dict[str, Any]]:
        normalized = answer.strip()
        if not normalized:
            return []

        statement = normalized.split("。")[0].strip()
        confidence = 0.6 if citations else 0.5
        return [
            {
                "query": query,
                "statement": statement,
                "confidence": confidence,
                "citations": citations,
            }
        ]
