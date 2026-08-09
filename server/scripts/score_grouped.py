"""Score ALL registered SME criteria via the skeleton-extraction (grouped) pass
against an SLM PDF (manual parity-testing tool).

This is the grouped-mode counterpart to score_criterion.py: instead of one
LLM call per criterion, it runs registry.run_grouped() -- 6 shared basket
calls (A1 assessment-centric, A2 task-centric, A3 monitoring, A4 enhancement,
B1 topics/transitions+feedback, B2 sections) -- and prints every criterion's
resulting score. Run score_criterion.py per-criterion (the validated oracle)
on the SAME file and compare scores to check parity. SME.run() now uses
run_grouped() unconditionally in the app; this script remains the manual
parity-testing tool.

Usage (from repo root):
    uv run --project server python server/scripts/score_grouped.py \
        --doc 32748c9d-445a-43a9-92e6-703a381ccd91.pdf
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fitz  # PyMuPDF  # noqa: E402

from server.core.llm import get_llm_client  # noqa: E402
from server.modules.agents.sme import registry  # noqa: E402

UPLOADS = ROOT / "uploads"

CRITERION_ORDER = (
    "A-01", "A-02", "A-03", "A-04", "A-05",
    "OP-01", "OP-02", "OP-03", "OP-04", "OP-05",
)


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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Score all registered SME criteria via the grouped/skeleton pass."
    )
    parser.add_argument(
        "--doc", required=True, help="PDF filename in uploads/ or a path"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=15.0,
        help="Seconds to wait between the 6 basket calls (rate-limit pacing, "
        "mirrors SME_SCORING_CALL_DELAY_SECONDS). Default 15.",
    )
    args = parser.parse_args()

    path = resolve_doc(args.doc)
    text = extract_text(path)
    print(f"SLM: {path.name} ({len(text)} chars)  |  mode: GROUPED (6 basket calls)")

    client = get_llm_client()
    results = registry.run_grouped(client, text, delay=args.delay)

    print()
    for code in CRITERION_ORDER:
        if code not in results:
            print(f"[{code}] MISSING -- basket failed or compute() raised for "
                  f"this criterion; per-criterion fallback would apply here.")
            continue
        score, justification, evidence = results[code]
        print(f"[{code}] SCORE {score}")
        print(f"        {justification}")
        for quote in evidence[:3]:
            print(f"        evidence: {quote[:120]}")
        print()

    missing = [c for c in CRITERION_ORDER if c not in results]
    if missing:
        print(f"({len(missing)} criteria missing from grouped result: "
              f"{', '.join(missing)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
