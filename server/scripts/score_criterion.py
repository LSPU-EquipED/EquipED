"""Score a single SME criterion against an SLM PDF (manual testing tool).

Usage (from repo root):
    uv run --project server python server/scripts/score_criterion.py \
        --doc 32748c9d-445a-43a9-92e6-703a381ccd91.pdf --criterion A-05

--doc may be a bare filename (looked up in uploads/) or a full path.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
# Ensure `server.*` is importable no matter where this script is launched from.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fitz  # PyMuPDF  # noqa: E402
from server.core.llm import get_llm_client  # noqa: E402
from server.modules.agents.scoring import objective_alignment  # noqa: E402
from server.modules.agents.scoring.objective_alignment import (  # noqa: E402
    AlignmentResult,
)

UPLOADS = ROOT / "uploads"

# Criterion code -> evaluator. Add criteria here as they are implemented.
CRITERIA: dict[str, Callable[[Any, str], AlignmentResult]] = {
    "A-05": objective_alignment.evaluate,
}


def extract_text(path: Path) -> str:
    parts: list[str] = []
    with fitz.open(path) as doc:
        for page in doc:
            parts.append(page.get_text() or "")
    return "\n".join(parts)


def resolve_doc(doc: str) -> Path:
    candidate = Path(doc)
    if candidate.is_file():
        return candidate
    in_uploads = UPLOADS / doc
    if in_uploads.is_file():
        return in_uploads
    raise SystemExit(f"Document not found: {doc} (also tried {in_uploads})")


def print_alignment(result: AlignmentResult) -> None:
    by_obj = {a.get("objective_id"): a for a in result.alignment}
    print(f"\nAssessments found ({result.total_assessments}):")
    for a in result.assessments:
        print(f"  [{a.get('id')}] {str(a.get('text', ''))[:120]}")

    print(f"\nObjectives & alignment ({result.total_objectives}):")
    for o in result.objectives:
        oid = o.get("id")
        info = by_obj.get(oid, {})
        measured = bool(info.get("is_measured"))
        mark = "ALIGNED" if measured else "MISSING"
        print(f"  [{mark}] obj[{oid}]: {str(o.get('text', ''))[:100]}")
        if measured:
            print(f"           evidence: {str(info.get('evidence', ''))[:120]}")

    pct = f"{result.pct:.0f}%" if result.pct is not None else "n/a"
    print(f"\naligned {result.aligned}/{result.total_objectives} = {pct}")
    print(f"==> SCORE {result.score}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Score one SME criterion on an SLM.")
    parser.add_argument(
        "--doc", required=True, help="PDF filename in uploads/ or a path"
    )
    parser.add_argument("--criterion", default="A-05", choices=sorted(CRITERIA))
    args = parser.parse_args()

    path = resolve_doc(args.doc)
    text = extract_text(path)
    print(f"SLM: {path.name} ({len(text)} chars)  |  criterion: {args.criterion}")

    evaluator = CRITERIA[args.criterion]
    result = evaluator(get_llm_client(), text)
    print_alignment(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
