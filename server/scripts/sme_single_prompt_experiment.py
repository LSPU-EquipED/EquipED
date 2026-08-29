"""THROWAWAY SPIKE — not wired into production.

Tests whether one combined LLM call (all 10 SME criteria, whole document,
no slicing) holds up, in the style of GAD's single-pass extraction. This
does NOT touch prompt_versions, groups.py, or the production SME pipeline —
it is a standalone probe to check for the same attention-degradation
failure that was diagnosed when SME's 3-category compaction was tried
(secondary criteria coming back empty/uniform). Run it, eyeball the output,
throw it away.

Usage (from repo root):
    uv run --project server python server/scripts/sme_single_prompt_experiment.py \
        --doc 32748c9d-445a-43a9-92e6-703a381ccd91.pdf
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fitz  # PyMuPDF  # noqa: E402

from server.core.config import get_settings  # noqa: E402
from server.core.llm import ResponseContract, get_llm_client  # noqa: E402
from server.modules.agents.runtime.llm import RunLLMClient  # noqa: E402
from server.modules.agents.sme.slicing import (  # noqa: E402
    downsample,
    slice_for_basket_a1,
)

UPLOADS = ROOT / "uploads"

CODES = (
    "a-01", "a-02", "a-03", "a-04", "a-05",
    "op-01", "op-02", "op-03", "op-04", "op-05",
)

INSTRUCTIONS = """You are a Subject Matter Expert (SME) content-accuracy scorer for Student Learning Materials (SLMs). Your role is to score all ten SME criteria against the provided document only.

TASK:
For each SME criterion below, examine document_text and assign a score from 1 to 4 following that criterion's scoring_rule exactly. State the count or percentage you found in the justification so the score is auditable. Ground all claims in document_text -- do not use external knowledge.

OUTPUT FORMAT:
Return a single JSON object with exactly ten keys: 'a-01', 'a-02', 'a-03', 'a-04', 'a-05', 'op-01', 'op-02', 'op-03', 'op-04', 'op-05'. Each section has: score (integer 1-4), justification (string, states the count/percentage found), evidence (array of exact verbatim quotes from document_text, max 8).

CRITERIA:

A-01 (Students are engaged in transforming what they learn):
- Score the percentage of tasks that engage higher-order thinking (apply/analyze/evaluate/create, not just remember/understand) on the moderate scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1. No tasks found -> 1.

A-02 (Teachers can easily assess students' progress by using varied assessment tools):
- Count distinct assessment TYPES used (objective test, written, reflection, performance task, project, oral, self-assessment). Score: 5+ types -> 4, 3-4 types -> 3, 2 types -> 2, <=1 type -> 1.

A-03 (The material keeps an on-going record of students' progress):
- Count genuine progress-monitoring mechanisms, spanning up to 4 types (checkpoint, self-assessment, reflection, cumulative). Score: 4+ mechanisms -> 4, 2-3 -> 3, 1 -> 2, 0 -> 1.

A-04 (Positive, meaningful feedback and prescriptive guides for interventions are provided):
- Count distinct feedback/intervention mechanism TYPES (answer key, rubric, remediation referral, positive reinforcement). Score: 3-4 types -> 4, 2 types -> 3, 1 type -> 2, 0 types -> 1.

A-05 (Objectives are gauged effectively):
- Score the percentage of stated objectives measured by a real assessment on the moderate scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1. No objectives found -> 1.

OP-01 (Topics are coherent from Unit to Chapter):
- If fewer than 4 topic-to-topic transitions total, score by issue count instead: 0 issues -> 4, 1 -> 3, 2 -> 2, 3+ -> 1. Otherwise, score the percentage of coherent transitions on the moderate scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1. No topics -> 1.

OP-02 (Material is interactive in each lesson):
- Count genuine interactive elements with real task content (not just a label like "Activity 1" with no task). Score: 4+ -> 4, 2-3 -> 3, 1 -> 2, 0 -> 1.

OP-03 (Directions are clear and complete enough for students to perform required tasks):
- Score the percentage of tasks with clear, complete directions on the moderate scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1.

OP-04 (Paragraphs and sections have clear and accurate information):
- Score the percentage of sections that are clear and internally consistent (no contradictions or garbled content) on the moderate scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1.

OP-05 (Enhancement activities for students are provided):
- Count genuine enhancement activities beyond the core lesson content. Score: 3+ -> 4, 2 -> 3, 1 -> 2, 0 -> 1.

CRITICAL RULES:
- Base ALL scores and evidence ONLY on the provided document_text.
- Every evidence entry must be an exact substring from document_text.
- Every justification must state the exact count or percentage found for that criterion, not just the score.
- All scores must be integers from 1 to 4.
- Return ONLY valid JSON. No markdown fences, no commentary outside the JSON object."""


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


def build_prompt(document_text: str) -> str:
    payload = {
        "agent": "sme",
        "document_text": document_text,
        "instructions": [INSTRUCTIONS],
    }
    return json.dumps(payload, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Spike: score all 10 SME criteria in one whole-document call."
    )
    parser.add_argument("--doc", required=True, help="PDF filename in uploads/ or a path")
    parser.add_argument(
        "--sliced",
        action="store_true",
        help="Use slicing.downsample() (existing document_wide strategy) "
        "instead of the raw whole document.",
    )
    parser.add_argument(
        "--combined",
        action="store_true",
        help="Concatenate the objectives-head+Performance-Tasks slice with "
        "the downsampled whole-document slice, so task-focused and "
        "document-wide criteria both get their needed content in one prompt.",
    )
    args = parser.parse_args()

    path = resolve_doc(args.doc)
    full_text = extract_text(path)
    if args.combined:
        head_and_tasks = slice_for_basket_a1(full_text, head=4000, body=9000)
        whole_doc_sample = downsample(full_text, budget=9000, windows=6)
        text = (
            "=== OBJECTIVES + PERFORMANCE TASKS SECTION ===\n"
            + head_and_tasks
            + "\n\n=== WHOLE-DOCUMENT SAMPLE (for coherence/consistency) ===\n"
            + whole_doc_sample
        )
        mode = "combined (head+tasks slice + downsample slice)"
    elif args.sliced:
        text = downsample(full_text, budget=9000, windows=6)
        mode = "downsampled (budget=9000, windows=6)"
    else:
        text = full_text
        mode = "raw whole document"
    print(
        f"SLM: {path.name} (full={len(full_text)} chars, sent={len(text)} chars, "
        f"mode={mode})  |  criteria: all 10, one call\n"
    )

    prompt = build_prompt(text)
    print(f"Prompt size: {len(prompt)} chars\n")

    settings = get_settings()
    client = RunLLMClient(
        get_llm_client(),
        "sme",
        default_response_contract=ResponseContract.json_object(),
    )
    completion = client.generate_result(
        prompt,
        temperature=settings.get_agent_temperature("sme"),
        max_new_tokens=settings.llm_max_new_tokens,
    )

    try:
        parsed = json.loads(completion.content)
    except json.JSONDecodeError as exc:
        print("!! Response was not valid JSON:")
        print(completion.content)
        raise SystemExit(1) from exc

    missing = [code for code in CODES if code not in parsed]
    if missing:
        print(f"!! Missing sections: {missing}")

    for code in CODES:
        section = parsed.get(code)
        if not isinstance(section, dict):
            print(f"\n[{code.upper()}] MISSING OR MALFORMED: {section!r}")
            continue
        score = section.get("score")
        justification = str(section.get("justification", "")).strip()
        evidence = section.get("evidence", [])
        print(f"\n[{code.upper()}] score={score}")
        print(f"  justification: {justification[:200]}")
        print(f"  evidence ({len(evidence) if isinstance(evidence, list) else 0}):")
        if isinstance(evidence, list):
            for e in evidence[:3]:
                print(f"    - {str(e)[:120]}")

    print(f"\nmodel served: {completion.served_model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
