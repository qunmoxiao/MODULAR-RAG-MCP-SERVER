"""Promote candidate facts by confidence thresholds."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


class FactPromoter:
    """Tiered promoter: promoted/candidate/rejected."""

    def __init__(self, promote_threshold: float, candidate_threshold: float) -> None:
        self.promote_threshold = promote_threshold
        self.candidate_threshold = candidate_threshold

    def classify(self, fact: Dict[str, Any]) -> str:
        score = float(fact.get("confidence", 0.0))
        if score >= self.promote_threshold:
            return "promoted"
        if score >= self.candidate_threshold:
            return "candidate"
        return "rejected"

    def split(self, facts: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        promoted: List[Dict[str, Any]] = []
        candidates: List[Dict[str, Any]] = []
        for fact in facts:
            bucket = self.classify(fact)
            if bucket == "promoted":
                promoted.append(fact)
            elif bucket == "candidate":
                candidates.append(fact)
        return promoted, candidates
