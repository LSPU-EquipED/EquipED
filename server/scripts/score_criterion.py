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
from server.modules.agents.scoring import (  # noqa: E402
    clear_directions,
    enhancement_activities,
    interactivity,
    objective_alignment,
)
from server.modules.agents.scoring.clear_directions import (  # noqa: E402
    DirectionsResult,
)
from server.modules.agents.scoring.enhancement_activities import (  # noqa: E402
    EnhancementResult,
)
from server.modules.agents.scoring.interactivity import (  # noqa: E402
    InteractivityResult,
)
from server.modules.agents.scoring.objective_alignment import (  # noqa: E402
    AlignmentResult,
)

UPLOADS = ROOT / "uploads"

# Criterion code -> evaluator. Add criteria here as they are implemented.
CRITERIA: dict[str, Callable[[Any, str], Any]] = {
    "A-05": objective_alignment.evaluate,
    "OP-02": interactivity.evaluate,
    "OP-03": clear_directions.evaluate,
    "OP-05": enhancement_activities.evaluate,
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


def print_interactivity(result: InteractivityResult) -> None:
    print(f"\nGenuine interactive elements ({result.count}):")
    for entry in result.genuine:
        label = str(entry.get("text", "")).strip()
        print(f"  - {label}")
        if entry.get("evidence"):
            print(f"      evidence: {str(entry.get('evidence', ''))[:120]}")

    dropped = len(result.elements) - result.count
    if dropped > 0:
        print(f"\n({dropped} listed element(s) dropped: no real content / duplicate)")

    print(f"\ncount {result.count}")
    print(f"==> SCORE {result.score}")


def print_directions(result: DirectionsResult) -> None:
    print(f"\nTasks & directions ({result.total}):")
    for t in result.tasks:
        clear = bool(t.get("has_clear_directions")) and bool(
            str(t.get("directions", "")).strip()
        )
        mark = "CLEAR" if clear else "UNCLEAR"
        print(f"  [{mark}] {str(t.get('text', '')).strip()[:100]}")
        if t.get("directions"):
            print(f"          directions: {str(t.get('directions', ''))[:120]}")

    pct = f"{result.pct:.0f}%" if result.pct is not None else "n/a"
    print(f"\nclear {result.clear}/{result.total} = {pct}")
    print(f"==> SCORE {result.score}")


def print_enhancement(result: EnhancementResult) -> None:
    print(f"\nEnhancement activities ({result.count}):")
    for entry in result.genuine:
        label = str(entry.get("text", "")).strip()
        print(f"  - {label}")
        if entry.get("evidence"):
            print(f"      evidence: {str(entry.get('evidence', ''))[:120]}")

    dropped = len(result.elements) - result.count
    if dropped > 0:
        print(f"\n({dropped} activity(ies) dropped: no real content / duplicate)")

    print(f"\ncount {result.count}")
    print(f"==> SCORE {result.score}")


def print_result(criterion: str, result: Any) -> None:
    if isinstance(result, InteractivityResult):
        print_interactivity(result)
    elif isinstance(result, DirectionsResult):
        print_directions(result)
    elif isinstance(result, EnhancementResult):
        print_enhancement(result)
    else:
        print_alignment(result)


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
    print_result(args.criterion, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
