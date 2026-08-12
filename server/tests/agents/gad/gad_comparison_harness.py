"""Controlled comparison harness for GAD single-pass vs multi-call scoring.

This harness compares two datasets (current multi-call and single-pass) without
making any live LLM calls. It accepts pre-recorded or synthetic results and
produces a structured report with runtime, criterion coverage, grounding
evidence, and deterministic scores.

Usage:
    harness = GADComparisonHarness()
    report = harness.compare(current_data, single_pass_data)
    # report is a dict with detailed comparisons

    # Or for quick validation:
    assert harness.scores_match(current_data, single_pass_data)
    assert harness.provenance_matches(current_data, single_pass_data)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class GADComparisonReport:
    """Structured comparison of current-vs-single-pass GAD scoring."""

    scores_match: bool
    """True if all five criterion scores are identical."""

    subtotal_match: bool
    """True if the subtotal (mean of scores) matches within tolerance."""

    evidence_volume_match: bool
    """True if accepted/rejected evidence counts match per criterion."""

    provenance_match: bool
    """True if registry_version and extraction_schema_version match."""

    criterion_coverage: dict[str, dict[str, Any]]
    """Per-criterion comparison: current_score, single_pass_score, match,
       current_evidence_count, single_pass_evidence_count,
       current_chunk_ids, single_pass_chunk_ids."""

    timing: dict[str, float]
    """Runtime breakdown: comparison_seconds, data_load_seconds."""

    registry_versions: dict[str, Any]
    """Registry version and schema version from both datasets."""

    discrepancies: list[str]
    """Human-readable list of any mismatches found."""

    @property
    def all_match(self) -> bool:
        return (
            self.scores_match
            and self.subtotal_match
            and self.evidence_volume_match
            and self.provenance_match
            and len(self.discrepancies) == 0
        )


@dataclass
class CriterionData:
    """Scoring data for a single GAD criterion from one dataset."""

    criterion_id: str
    criterion_title: str
    score: int
    justification: str
    evidence: tuple[str, ...] = ()
    chunk_ids: tuple[str, ...] = ()


@dataclass
class GADResultData:
    """Normalized GAD scoring result from one dataset."""

    criteria: list[CriterionData]
    subtotal: float
    model_name: str
    processing_seconds: float
    token_count: int
    evidence_candidates: int
    evidence_accepted: int
    evidence_rejected: int
    registry_version: int
    extraction_schema_version: str
    scoring_mode: str
    llm_call_count: int
    success: bool


def _normalize_criterion_score(data: dict[str, Any]) -> CriterionData:
    """Normalize a single criterion score dict into CriterionData."""
    return CriterionData(
        criterion_id=str(data.get("criterion_id", "")),
        criterion_title=str(data.get("criterion_title", "")),
        score=int(data.get("score", 0)),
        justification=str(data.get("justification", "")),
        evidence=tuple(data.get("evidence", []) or []),
        chunk_ids=tuple(data.get("chunk_ids", []) or []),
    )


def normalize_result(result: dict[str, Any]) -> GADResultData:
    """Convert raw result dict (from either dataset) into GADResultData.

    The dict can come from:
    - An ``AgentEvaluationResult`` dict (e.g. from the supervisor)
    - A manually constructed comparison fixture
    """
    raw_criteria = result.get("criterion_scores", []) or []
    criteria = [_normalize_criterion_score(c) for c in raw_criteria]

    meta = result.get("metadata", {}) or {}

    prov = result.get("provenance", {}) or {}

    return GADResultData(
        criteria=criteria,
        subtotal=float(result.get("subtotal", 0.0)),
        model_name=str(prov.get("actual_model", result.get("model_name", ""))),
        processing_seconds=float(result.get("processing_seconds", 0.0)),
        token_count=int(result.get("token_count", 0)),
        evidence_candidates=int(prov.get("evidence_candidates", 0)),
        evidence_accepted=int(prov.get("evidence_accepted", 0)),
        evidence_rejected=int(prov.get("evidence_rejected", 0)),
        registry_version=int(prov.get("registry_version", 0)),
        extraction_schema_version=str(prov.get("extraction_schema_version", "")),
        scoring_mode=str(meta.get("scoring_mode", "")),
        llm_call_count=int(meta.get("llm_call_count", 0)),
        success=bool(result.get("success", True)),
    )


class GADComparisonHarness:
    """Controlled comparison harness for GAD scoring.

    Compares two datasets without live LLM calls. Accepts raw result dicts
    or pre-normalized ``GADResultData`` objects.
    """

    SCORE_TOLERANCE = 1e-9
    SUBTOTAL_TOLERANCE = 0.01
    VALID_CRITERION_IDS = frozenset({"GAD-01", "GAD-02", "GAD-03", "GAD-04", "GAD-05"})

    def __init__(self) -> None:
        self._timings: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Public comparison API
    # ------------------------------------------------------------------

    def compare(
        self,
        current: dict[str, Any] | GADResultData,
        single_pass: dict[str, Any] | GADResultData,
    ) -> GADComparisonReport:
        """Compare two GAD scoring datasets and return a structured report.

        Args:
            current: The current multi-call result (dict or GADResultData).
            single_pass: The single-pass result (dict or GADResultData).

        Returns:
            ``GADComparisonReport`` with per-criterion and aggregate comparisons.
        """
        t_start = time.perf_counter()

        cur = self._ensure_normalized(current)
        sp = self._ensure_normalized(single_pass)

        # Version check
        provenance_match = (
            cur.registry_version == sp.registry_version
            and cur.extraction_schema_version == sp.extraction_schema_version
        )

        # Per-criterion comparison
        cur_by_id = {c.criterion_id: c for c in cur.criteria}
        sp_by_id = {c.criterion_id: c for c in sp.criteria}

        all_ids = self.VALID_CRITERION_IDS
        criterion_coverage: dict[str, dict[str, Any]] = {}
        discrepancies: list[str] = []
        scores_match = True
        evidence_volume_match = True

        for cid in sorted(all_ids):
            cc = cur_by_id.get(cid)
            sc = sp_by_id.get(cid)

            if cc is None and sc is None:
                criterion_coverage[cid] = {
                    "current_score": None,
                    "single_pass_score": None,
                    "match": "missing_both",
                    "current_evidence_count": None,
                    "single_pass_evidence_count": None,
                }
                discrepancies.append(f"{cid}: missing from both datasets")
                continue

            if cc is None:
                criterion_coverage[cid] = {
                    "current_score": None,
                    "single_pass_score": sc.score if sc else None,
                    "match": "missing_current",
                    "current_evidence_count": None,
                    "single_pass_evidence_count": len(sc.evidence) if sc else None,
                }
                discrepancies.append(f"{cid}: missing from current dataset")
                scores_match = False
                continue

            if sc is None:
                criterion_coverage[cid] = {
                    "current_score": sc.score if sc else None,
                    "single_pass_score": None,
                    "match": "missing_single_pass",
                    "current_evidence_count": len(cc.evidence) if cc else None,
                    "single_pass_evidence_count": None,
                }
                discrepancies.append(f"{cid}: missing from single-pass dataset")
                scores_match = False
                continue

            score_ok = abs(cc.score - sc.score) <= self.SCORE_TOLERANCE
            if not score_ok:
                scores_match = False
                discrepancies.append(f"{cid}: score mismatch {cc.score} vs {sc.score}")

            ev_ok = len(cc.evidence) == len(sc.evidence)
            if not ev_ok:
                evidence_volume_match = False
                discrepancies.append(
                    f"{cid}: evidence count mismatch "
                    f"{len(cc.evidence)} vs {len(sc.evidence)}"
                )

            criterion_coverage[cid] = {
                "current_score": cc.score,
                "single_pass_score": sc.score,
                "match": score_ok,
                "current_evidence_count": len(cc.evidence),
                "single_pass_evidence_count": len(sc.evidence),
                "current_chunk_ids": list(cc.chunk_ids),
                "single_pass_chunk_ids": list(sc.chunk_ids),
                "current_justification": cc.justification,
                "single_pass_justification": sc.justification,
                "current_evidence": list(cc.evidence),
                "single_pass_evidence": list(sc.evidence),
            }

        # Subtotal comparison
        subtotal_match = abs(cur.subtotal - sp.subtotal) <= self.SUBTOTAL_TOLERANCE
        if not subtotal_match:
            discrepancies.append(
                f"subtotal mismatch: {cur.subtotal:.4f} vs {sp.subtotal:.4f}"
            )

        self._timings["comparison_seconds"] = time.perf_counter() - t_start

        return GADComparisonReport(
            scores_match=scores_match,
            subtotal_match=subtotal_match,
            evidence_volume_match=evidence_volume_match,
            provenance_match=provenance_match,
            criterion_coverage=criterion_coverage,
            timing=self._timings.copy(),
            registry_versions={
                "current_registry_version": cur.registry_version,
                "single_pass_registry_version": sp.registry_version,
                "current_extraction_schema_version": (cur.extraction_schema_version),
                "single_pass_extraction_schema_version": (sp.extraction_schema_version),
            },
            discrepancies=discrepancies,
        )

    def scores_match(
        self,
        current: dict[str, Any] | GADResultData,
        single_pass: dict[str, Any] | GADResultData,
    ) -> bool:
        """Quick check: do all five criterion scores match?"""
        return self.compare(current, single_pass).scores_match

    def provenance_matches(
        self,
        current: dict[str, Any] | GADResultData,
        single_pass: dict[str, Any] | GADResultData,
    ) -> bool:
        """Quick check: do registry versions match?"""
        return self.compare(current, single_pass).provenance_match

    def evidence_volumes_match(
        self,
        current: dict[str, Any] | GADResultData,
        single_pass: dict[str, Any] | GADResultData,
    ) -> bool:
        """Quick check: do per-criterion evidence counts match?"""
        return self.compare(current, single_pass).evidence_volume_match

    # ------------------------------------------------------------------
    # Reporting helpers
    # ------------------------------------------------------------------

    def summary(self, report: GADComparisonReport) -> str:
        """Return a short human-readable summary of the comparison."""
        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("GAD Single-Pass Comparison Report")
        lines.append("=" * 60)
        lines.append(f"All scores match:      {report.scores_match}")
        lines.append(f"Subtotal match:        {report.subtotal_match}")
        lines.append(f"Evidence volumes match: {report.evidence_volume_match}")
        lines.append(f"Provenance match:      {report.provenance_match}")
        lines.append(f"Discrepancy count:     {len(report.discrepancies)}")
        lines.append("")

        for cid, cov in sorted(report.criterion_coverage.items()):
            s = cov.get("match", "?")
            if isinstance(s, bool):
                s = "✓" if s else "✗"
            lines.append(
                f"  {cid}: current={cov.get('current_score')} "
                f"single-pass={cov.get('single_pass_score')} "
                f"[{s}]"
            )

        if report.discrepancies:
            lines.append("")
            lines.append("Discrepancies:")
            for d in report.discrepancies:
                lines.append(f"  - {d}")

        lines.append("")
        lines.append("Registry versions:")
        rv = report.registry_versions
        lines.append(
            f"  Current:     v{rv.get('current_registry_version')} / "
            f"schema {rv.get('current_extraction_schema_version')}"
        )
        lines.append(
            f"  Single-pass: v{rv.get('single_pass_registry_version')} / "
            f"schema {rv.get('single_pass_extraction_schema_version')}"
        )

        lines.append("")
        lines.append(
            f"Comparison took {report.timing.get('comparison_seconds', 0):.4f}s"
        )
        return "\n".join(lines)

    def detailed_markdown(self, report: GADComparisonReport) -> str:
        """Return a detailed markdown report."""
        lines: list[str] = []
        lines.append("# GAD Single-Pass Comparison Report")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Scores match:** {report.scores_match}")
        lines.append(f"- **Subtotal match:** {report.subtotal_match}")
        lines.append(f"- **Evidence volumes match:** {report.evidence_volume_match}")
        lines.append(f"- **Provenance match:** {report.provenance_match}")
        lines.append(f"- **Discrepancies:** {len(report.discrepancies)}")
        lines.append("")

        lines.append("## Per-Criterion Comparison")
        lines.append("")
        lines.append(
            "| Criterion | Current | Single-Pass | Match | Evidence Cur | Evidence SP |"
        )
        lines.append(
            "|-----------|--------:|------------:|:-----:|-------------:|------------:|"
        )

        for cid in sorted(report.criterion_coverage):
            cov = report.criterion_coverage[cid]
            s = cov.get("match", "?")
            match_str = "✓" if s is True else ("✗" if s is False else str(s))
            lines.append(
                f"| {cid} | {cov.get('current_score', '')} | "
                f"{cov.get('single_pass_score', '')} | {match_str} | "
                f"{cov.get('current_evidence_count', '')} | "
                f"{cov.get('single_pass_evidence_count', '')} |"
            )

        lines.append("")
        lines.append("## Discrepancies")
        lines.append("")
        if report.discrepancies:
            for d in report.discrepancies:
                lines.append(f"- {d}")
        else:
            lines.append("*None*")

        lines.append("")
        lines.append("## Registry Versions")
        lines.append("")
        rv = report.registry_versions
        lines.append(f"- Current registry: v{rv.get('current_registry_version')}")
        lines.append(f"- Current schema: {rv.get('current_extraction_schema_version')}")
        lines.append(
            f"- Single-pass registry: v{rv.get('single_pass_registry_version')}"
        )
        lines.append(
            f"- Single-pass schema: {rv.get('single_pass_extraction_schema_version')}"
        )

        lines.append("")
        lines.append("## Timing")
        lines.append("")
        lines.append(f"- Comparison: {report.timing.get('comparison_seconds', 0):.4f}s")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_normalized(self, data: dict[str, Any] | GADResultData) -> GADResultData:
        """Normalize input to GADResultData."""
        if isinstance(data, GADResultData):
            return data
        return normalize_result(data)


__all__ = [
    "GADComparisonHarness",
    "GADComparisonReport",
    "GADResultData",
    "CriterionData",
    "normalize_result",
]
