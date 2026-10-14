"""Offline ITSO consistency benchmark harness.

Runs ITSO prechecks, prompt assembly, and agent execution with a
deterministic fake LLM client, then reports criterion-score deltas
across repeat runs and provenance.  No live provider or database calls.

Usage (from repo root):

    cd apps && uv run --project server python -m \\
        server.scripts.run_itso_benchmark
    cd apps && uv run --project server python -m \\
        server.scripts.run_itso_benchmark --runs 10
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from equiped_harness import (  # noqa: E402
    CompletionResult,
    EvaluationRequest,
    ExecutionConfig,
    evaluate,
    run_itso_precheck,
)
from equiped_harness.contracts import (  # noqa: E402
    CriterionDefinition,
    DomainDefinition,
    FormDefinition,
    LlmRubricGuidanceConfig,
)
from equiped_harness.result_contracts import AgentEvaluationResult  # noqa: E402
from equiped_harness.snapshot_contracts import (  # noqa: E402
    build_evaluation_form_snapshot,
)

# ---------------------------------------------------------------------------
# Fixtures — known, reproducible SLM-like text and chunk data
# ---------------------------------------------------------------------------

SLM_TEXT_WITH_CITATIONS = (
    "Understanding cybersecurity threats is critical for modern organisations. "
    "Several studies confirm this finding (Author, 2020). "
    "Another work supports it (Writer et al., 2019). "
    "Research also shows [1] that the effect is significant. "
    "Multiple sources [2, 3, 4] confirm these results. "
    "A comprehensive review (Scientist, 2021) further validates the approach. "
    "The DOI 10.1234/abcdef provides additional context on this topic.\n\n"
    "References\n"
    "Author, A. (2020). Understanding cybersecurity threats. "
    "Journal of Security, 15(2), 100-110.\n"
    "Writer, B. (2019). Network security fundamentals. Computing Press.\n"
    "Scientist, C. (2021). Modern threat detection. "
    "Cybersecurity Today, 8(4), 45-58.\n"
    "Researcher, D. (2018). Data protection in higher education. "
    "LSPU Research Journal, 12(1), 20-30.\n"
    "Analyst, E. (2022). Privacy frameworks in education. "
    "International Journal of EdTech, 5(3), 78-89.\n"
)

SLM_TEXT_NO_CITATIONS = (
    "This document covers basic concepts in information technology. "
    "Students will learn about computer hardware, software, and networking. "
    "The course is designed for first-year college students. "
    "Topics include operating systems, databases, and web development. "
    "Assessment methods include written exams and practical projects."
)

CHUNK_INFOS_WITH_CITATIONS: list[dict[str, Any]] = [
    {
        "chunk_id": "chunk-001",
        "page_number": 1,
        "text": SLM_TEXT_WITH_CITATIONS,
    },
]

CHUNK_INFOS_NO_CITATIONS: list[dict[str, Any]] = [
    {
        "chunk_id": "chunk-001",
        "page_number": 1,
        "text": SLM_TEXT_NO_CITATIONS,
    },
]

# ---------------------------------------------------------------------------
# Deterministic fake LLM client
# ---------------------------------------------------------------------------

_DEFAULT_FAKE_RESPONSE = json.dumps(
    {
        "summary": "The SLM demonstrates adequate security awareness "
        "and proper academic referencing.",
        "criterion_scores": [
            {
                "criterion_id": "ITSO-01",
                "criterion_title": "No IP Issue",
                "score": 3,
                "justification": "Citations are present and consistent.",
                "chunk_ids": ["chunk-001"],
                "evidence": ["Several studies confirm this finding (Author, 2020)."],
            },
            {
                "criterion_id": "ITSO-02",
                "criterion_title": "Proper References",
                "score": 3,
                "justification": "Bibliography section present with 5 entries.",
                "chunk_ids": ["chunk-001"],
                "evidence": ["References\nAuthor, A. (2020). Understanding..."],
            },
            {
                "criterion_id": "ITSO-03",
                "criterion_title": "Faculty Ownership",
                "score": 3,
                "justification": "Content appears original.",
                "chunk_ids": ["chunk-001"],
                "evidence": [],
            },
            {
                "criterion_id": "ITSO-04",
                "criterion_title": "Student Confidentiality",
                "score": 3,
                "justification": "No student data exposed in this sample.",
                "chunk_ids": ["chunk-001"],
                "evidence": [],
            },
            {
                "criterion_id": "ITSO-05",
                "criterion_title": "Teacher and Student Rights",
                "score": 3,
                "justification": "Digital rights appear preserved.",
                "chunk_ids": ["chunk-001"],
                "evidence": [],
            },
        ],
    }
)


class DeterministicFakeLLM:
    """Fake LLM that always returns the same valid JSON response.

    ``model`` attribute is set so the agent's provenance capture works.
    """

    model = "benchmark-fake-model"

    def __init__(self, response_json: str | None = None) -> None:
        self._response = response_json or _DEFAULT_FAKE_RESPONSE

    def generate_result(
        self,
        prompt,
        *,
        temperature,
        max_new_tokens,
        deadline=None,
        response_contract=None,
    ) -> CompletionResult:
        return CompletionResult(self._response, self.model)


class VariedFakeLLM:
    """Fake LLM that cycles through a list of responses for each call.

    ``model`` attribute is set so the agent's provenance capture works.
    """

    model = "benchmark-varied-model"

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self._call_count = 0

    def generate_result(
        self,
        prompt,
        *,
        temperature,
        max_new_tokens,
        deadline=None,
        response_contract=None,
    ) -> CompletionResult:
        idx = self._call_count % len(self._responses)
        self._call_count += 1
        return CompletionResult(self._responses[idx], self.model)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Benchmark runs
# ---------------------------------------------------------------------------


def run_precheck_benchmark(text: str, *, runs: int = 5) -> dict[str, Any]:
    """Run precheck on the same text N times; verify hash stability.

    Returns a summary dict with drift info.
    """
    results: list[dict[str, Any]] = []
    for i in range(runs):
        result = run_itso_precheck(text)
        results.append(dict(result))

    first_hash = results[0]["result_hash"]
    all_same = all(r["result_hash"] == first_hash for r in results)

    return {
        "name": "precheck",
        "runs": runs,
        "stable": all_same,
        "result_hash": first_hash,
        "details": {
            "bibliography_found": results[0]["bibliography_found"],
            "reference_count": results[0]["reference_count"],
            "intext_citation_count": results[0]["intext_citation_count"],
            "doi_count": results[0]["doi_count"],
            "coverage_ratio": results[0]["coverage_ratio"],
        },
    }


def _normalize_result(result: AgentEvaluationResult) -> dict[str, Any]:
    """Extract comparable fields from an AgentEvaluationResult."""
    return {
        "subtotal": result.subtotal,
        "criterion_scores": [
            {
                "criterion_id": s.criterion_id,
                "score": s.score,
                "justification": s.justification[:80],
            }
            for s in result.criterion_scores
        ],
        "model_name": result.model_name,
        "success": result.success,
    }


def run_agent_benchmark(
    chunk_infos: list[dict[str, Any]],
    provenance: dict[str, Any] | None = None,
    *,
    runs: int = 3,
    fake_llm: Any = None,
) -> dict[str, Any]:
    """Run ITSO agent with deterministic fake LLM N times.

    Returns a summary with per-run results and drift detection.
    """
    config = ExecutionConfig(agent_total_prompt_budget_chars=8000)

    if fake_llm is None:
        fake_llm = DeterministicFakeLLM()

    # Supply prepared context explicitly; the library never queries storage.
    precomputed_context = {"rubric_itso": []}

    results: list[dict[str, Any]] = []
    for i in range(runs):
        evaluation_id = uuid4()
        rows = json.loads(_DEFAULT_FAKE_RESPONSE)["criterion_scores"]
        form = FormDefinition(
            rubric_set_id=uuid4(),
            agent_id="itso",
            adapter_key="itso",
            adapter_version=1,
            name="Deterministic ITSO benchmark",
            version_number=1,
            domains=(
                DomainDefinition(
                    rubric_domain_id=uuid4(),
                    code="ITSO",
                    title="ITSO",
                    display_order=1,
                    criteria=tuple(
                        CriterionDefinition(
                            rubric_criterion_id=uuid4(),
                            criterion_code=row["criterion_id"],
                            title=row["criterion_title"],
                            description=row["criterion_title"],
                            display_order=index,
                            strategy_config=LlmRubricGuidanceConfig(
                                guidance=row["criterion_title"]
                            ),
                        )
                        for index, row in enumerate(rows)
                    ),
                ),
            ),
        )
        result = evaluate(
            EvaluationRequest(
                evaluation_id=evaluation_id,
                document_id=uuid4(),
                chunk_infos=chunk_infos,
                form_snapshot=build_evaluation_form_snapshot(evaluation_id, form),
                provenance=provenance,
                precomputed_context=precomputed_context,
            ),
            fake_llm,
            config,
        )
        results.append(_normalize_result(result))

    # Detect drift.
    first = results[0]
    deltas: list[dict[str, Any]] = []
    for i in range(1, runs):
        sd = results[i]["subtotal"] - first["subtotal"]
        run_deltas: dict[str, Any] = {
            "run": i,
            "subtotal_delta": sd,
            "criterion_deltas": [],
        }
        pairs = zip(first["criterion_scores"], results[i]["criterion_scores"])
        for f, r in pairs:
            if f["score"] != r["score"]:
                run_deltas["criterion_deltas"].append(
                    {
                        "criterion_id": f["criterion_id"],
                        "expected_score": f["score"],
                        "actual_score": r["score"],
                    }
                )
        deltas.append(run_deltas)

    all_zero_drift = all(
        d["subtotal_delta"] == 0 and not d["criterion_deltas"] for d in deltas
    )

    return {
        "name": "agent",
        "runs": runs,
        "zero_drift": all_zero_drift,
        "results": results,
        "deltas": deltas,
        "details": {
            "first_subtotal": first["subtotal"],
            "criterion_count": len(first["criterion_scores"]),
        },
    }


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def _format_summary(reports: list[dict[str, Any]]) -> str:
    """Format benchmark reports into a human-readable summary."""
    lines: list[str] = [
        "=" * 60,
        "  ITSO Consistency Benchmark Summary",
        "=" * 60,
        "",
    ]

    for report in reports:
        lines.append(f"--- {report['name']} benchmark ({report['runs']} runs) ---")
        if report["name"] == "precheck":
            status = "STABLE" if report["stable"] else "DRIFT DETECTED"
            lines.append(f"  Hash: {report['result_hash'][:16]}...  {status}")
            d = report["details"]
            lines.append(f"  bibliography: {d['bibliography_found']}")
            lines.append(f"  references: {d['reference_count']}")
            lines.append(f"  citations: {d['intext_citation_count']}")
            lines.append(f"  DOIs: {d['doi_count']}")
            lines.append(f"  coverage: {d['coverage_ratio']:.2f}")
        elif report["name"] == "agent":
            status = "ZERO DRIFT" if report["zero_drift"] else "DRIFT DETECTED"
            lines.append(f"  Subtotal: {report['details']['first_subtotal']}  {status}")
            lines.append(f"  Criteria: {report['details']['criterion_count']}")
            if not report["zero_drift"]:
                for d in report["deltas"]:
                    if d["subtotal_delta"] != 0 or d["criterion_deltas"]:
                        lines.append(
                            f"  Run {d['run']}: subtotal delta={d['subtotal_delta']}"
                        )
                        for cd in d["criterion_deltas"]:
                            lines.append(
                                f"    {cd['criterion_id']}: "
                                f"expected={cd['expected_score']} "
                                f"actual={cd['actual_score']}"
                            )
        lines.append("")

    lines.append("=" * 60)
    lines.append("  Advisory: Live provider runs (e.g. Groq) may differ ")
    lines.append("  even at temperature 0 due to provider-level variation.")
    lines.append("=" * 60)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ITSO offline consistency benchmark harness."
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Number of repeat iterations (default: 5)",
    )
    parser.add_argument(
        "--no-precheck",
        action="store_true",
        help="Skip the precheck stability benchmark",
    )
    args = parser.parse_args()

    reports: list[dict[str, Any]] = []

    # --- Precheck benchmark ---
    if not args.no_precheck:
        precheck_report = run_precheck_benchmark(
            SLM_TEXT_WITH_CITATIONS, runs=args.runs
        )
        reports.append(precheck_report)

    # --- Agent benchmark (with-citations fixture) ---
    provenance_with = {
        "precheck_version": "1",
        "bibliography_found": True,
        "reference_count": 5,
        "intext_citation_count": 4,
        "doi_count": 1,
        "coverage_ratio": 0.8,
    }
    agent_report = run_agent_benchmark(
        CHUNK_INFOS_WITH_CITATIONS,
        provenance=provenance_with,
        runs=max(3, args.runs),
    )
    reports.append(agent_report)

    print(_format_summary(reports))
    return (
        0
        if all(r.get("stable", True) and r.get("zero_drift", True) for r in reports)
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
