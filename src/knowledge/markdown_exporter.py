"""Export wiki facts to markdown."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


class MarkdownExporter:
    """Dual-write markdown export for auditability."""

    def __init__(self, base_dir: str) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def export_facts(self, facts: List[Dict[str, Any]]) -> Path:
        output = self.base_dir / "facts.md"
        lines = ["# Structured Facts", ""]
        for fact in facts:
            lines.append(f"- {fact.get('statement', '')}")
            lines.append(f"  - confidence: {fact.get('confidence', 0.0)}")
            citations = ", ".join(fact.get("citations", []))
            lines.append(f"  - citations: {citations}")
        output.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return output
