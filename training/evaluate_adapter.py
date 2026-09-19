"""Compare a GGUF LoRA adapter with the plain model on held-out DPO pairs.

Each held-out pair is a case a reviewer corrected: `rejected` is the model's
original SME/Coordinator reply and `chosen` is the same reply with the
reviewer's scores. This script sends every held-out prompt to a running
llama-server twice -- adapter off (scale 0) and adapter on (scale 1) -- and
checks which reply lands closer to the reviewer's corrected scores. A
two-sided sign test on the per-pair wins and losses turns that into a verdict:
better, worse or inconclusive.

Usage:
    python training/evaluate_adapter.py --adapter-zip adapter.zip \
        --base-url http://127.0.0.1:8080/v1 --report-json report.json

The held-out set comes from `heldout_pairs.jsonl` inside the adapter zip (the
DPO training notebook writes it) or from a bare file via --heldout.

Server options, environment fallbacks (LLM_API_BASE, LLM_API_KEY,
LLM_MODEL_NAME), the scale modes and the global-scale reset all work as in
training/smoke_test_lora_serving.py, whose client this script reuses.

Exit code: 0 the adapter is better, 1 worse or inconclusive, 2 could not run
(server unreachable, no adapter loaded, no held-out set, bad input).

What a verdict means: the held-out pairs are only cases reviewers CHANGED, so
this measures whether the adapter fixes known mistakes, not whether it harms
cases reviewers approved. Only the criterion_measurements reply shape (SME and
Coordinator) is supported.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import math
import os
import sys
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import smoke_test_lora_serving as smoke

HELDOUT_FILENAME = "heldout_pairs.jsonl"
TRAINING_MANIFEST_FILENAME = "training_manifest.json"
DEFAULT_MIN_DECISIVE = 20
DEFAULT_ALPHA = 0.05
DEFAULT_MAX_TOKENS = 2048
# A missing, unparsable or out-of-range answer is as wrong as a score can be.
WORST_ERROR = smoke.MAX_SCORE - smoke.MIN_SCORE
# Refuse to read absurdly large members out of a zip.
MAX_MEMBER_BYTES = 64 * 1024 * 1024

LIMITS_NOTE = (
    "Limits: the held-out pairs are only cases reviewers CHANGED, so this "
    "measures fixing known mistakes, not harm to cases reviewers approved. "
    "With few pairs a verdict is weak evidence."
)


def answer_key(chosen: str, rejected: str) -> dict[str, int] | None:
    """The reviewer's score for every criterion they changed, else None.

    A criterion is in the key when it appears in both replies and its score
    differs; the value is the score in `chosen`. None means the pair cannot be
    scored (an unparsable reply, or no changed score).
    """
    chosen_result = smoke.validate_sme_reply(chosen)
    rejected_result = smoke.validate_sme_reply(rejected)
    if not (chosen_result.valid and rejected_result.valid):
        return None
    key = {
        criterion_id: score
        for criterion_id, score in chosen_result.scores.items()
        if criterion_id in rejected_result.scores
        and rejected_result.scores[criterion_id] != score
    }
    return key or None


def error_total(key: dict[str, int], scores: dict[str, int] | None) -> int:
    """Sum of |score - reviewer's score| over the key.

    `scores` is None for an invalid reply; a criterion the reply lacks is also
    counted at the worst error.
    """
    if scores is None:
        return WORST_ERROR * len(key)
    return sum(
        abs(scores[criterion_id] - gold)
        if criterion_id in scores
        else WORST_ERROR
        for criterion_id, gold in key.items()
    )


@dataclass(frozen=True)
class PairScore:
    pair_id: str
    gold: dict[str, int]
    base_scores: dict[str, int] | None
    adapter_scores: dict[str, int] | None
    base_error: float
    adapter_error: float
    outcome: str  # "win" | "loss" | "tie" -- from the adapter's point of view


def score_pair(
    pair_id: str,
    key: dict[str, int],
    base_scores: dict[str, int] | None,
    adapter_scores: dict[str, int] | None,
) -> PairScore:
    base_total = error_total(key, base_scores)
    adapter_total = error_total(key, adapter_scores)
    if adapter_total < base_total:
        outcome = "win"
    elif adapter_total > base_total:
        outcome = "loss"
    else:
        outcome = "tie"
    return PairScore(
        pair_id=pair_id,
        gold=dict(key),
        base_scores=base_scores,
        adapter_scores=adapter_scores,
        base_error=base_total / len(key),
        adapter_error=adapter_total / len(key),
        outcome=outcome,
    )


def sign_test_p(wins: int, losses: int) -> float:
    """Exact two-sided sign test p-value; ties are not part of the input."""
    decisive = wins + losses
    if decisive == 0:
        return 1.0
    tail = sum(math.comb(decisive, i) for i in range(min(wins, losses) + 1))
    return min(1.0, 2 * tail / 2**decisive)


@dataclass(frozen=True)
class Verdict:
    verdict: str  # "better" | "worse" | "inconclusive"
    reasons: tuple[str, ...]
    p_value: float


def decide(
    wins: int,
    losses: int,
    base_valid_rate: float,
    adapter_valid_rate: float,
    *,
    min_decisive: int,
    alpha: float,
) -> Verdict:
    decisive = wins + losses
    p_value = sign_test_p(wins, losses)
    if decisive < min_decisive:
        return Verdict(
            "inconclusive",
            (f"too few decisive pairs ({decisive} < {min_decisive})",),
            p_value,
        )
    if p_value >= alpha:
        return Verdict(
            "inconclusive",
            (
                f"the difference is not statistically significant "
                f"(p={p_value:.4f}, alpha={alpha})",
            ),
            p_value,
        )
    if losses > wins:
        return Verdict(
            "worse",
            (f"adapter lost {losses} and won {wins} decisive pairs (p={p_value:.4f})",),
            p_value,
        )
    if adapter_valid_rate < base_valid_rate:
        return Verdict(
            "inconclusive",
            (
                f"adapter won {wins} and lost {losses} decisive pairs "
                f"(p={p_value:.4f}) but returns invalid JSON more often than "
                "the plain model",
            ),
            p_value,
        )
    return Verdict(
        "better",
        (f"adapter won {wins} and lost {losses} decisive pairs (p={p_value:.4f})",),
        p_value,
    )


@dataclass(frozen=True)
class HeldoutPair:
    pair_id: str
    evaluation_id: str
    prompt: str
    chosen: str
    rejected: str


@dataclass(frozen=True)
class HeldoutSet:
    pairs: tuple[HeldoutPair, ...]
    source: str
    sha256: str
    sha256_verified: bool
    adapter_zip_sha256: str | None = None


_HELDOUT_FIELDS = ("pair_id", "evaluation_id", "prompt", "chosen", "rejected")


def parse_heldout(data: bytes) -> tuple[HeldoutPair, ...]:
    """Parse the bytes of a heldout_pairs.jsonl file."""
    pairs: list[HeldoutPair] = []
    for line_number, line in enumerate(data.decode("utf-8").split("\n"), start=1):
        if not line.strip():
            continue
        where = f"{HELDOUT_FILENAME} line {line_number}"
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{where}: not valid JSON: {exc.msg}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{where}: not a JSON object")
        for name in _HELDOUT_FIELDS:
            value = row.get(name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{where}: missing or empty {name!r}")
        pairs.append(HeldoutPair(**{name: row[name] for name in _HELDOUT_FIELDS}))
    if not pairs:
        raise ValueError(f"{HELDOUT_FILENAME} contains no pairs")
    return tuple(pairs)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_heldout_file(path: Path) -> HeldoutSet:
    """A bare heldout_pairs.jsonl: nothing to verify it against."""
    data = Path(path).read_bytes()
    return HeldoutSet(
        pairs=parse_heldout(data),
        source=str(path),
        sha256=hashlib.sha256(data).hexdigest(),
        sha256_verified=False,
    )


def _read_member(archive: zipfile.ZipFile, name: str) -> bytes:
    try:
        info = archive.getinfo(name)
    except KeyError:
        raise ValueError(f"{name} is not in the adapter zip") from None
    if info.file_size > MAX_MEMBER_BYTES:
        raise ValueError(f"{name} in the adapter zip is too large to read")
    return archive.read(name)


def load_heldout_zip(path: Path) -> HeldoutSet:
    """The held-out set of an adapter zip, checked against its manifest."""
    with zipfile.ZipFile(path) as archive:
        manifest_bytes = _read_member(archive, TRAINING_MANIFEST_FILENAME)
        try:
            manifest = json.loads(manifest_bytes.decode("utf-8"))
        except ValueError as exc:
            raise ValueError(
                f"{TRAINING_MANIFEST_FILENAME} in the adapter zip is not valid JSON"
            ) from exc
        heldout = manifest.get("heldout") if isinstance(manifest, dict) else None
        if not isinstance(heldout, dict):
            raise ValueError(
                "this adapter has no held-out set (it was trained on fewer than "
                "20 pairs, from a single evaluation, or with a notebook that "
                "predates the grouped split); pass --heldout to use another file"
            )
        data = _read_member(archive, HELDOUT_FILENAME)
    actual_sha256 = hashlib.sha256(data).hexdigest()
    if actual_sha256 != heldout.get("sha256"):
        raise ValueError(
            f"{HELDOUT_FILENAME} does not match the sha256 recorded in "
            f"{TRAINING_MANIFEST_FILENAME}; the adapter zip was modified"
        )
    pairs = parse_heldout(data)
    if heldout.get("pair_count") != len(pairs):
        raise ValueError(
            f"{TRAINING_MANIFEST_FILENAME} says {heldout.get('pair_count')} "
            f"held-out pairs but {HELDOUT_FILENAME} has {len(pairs)}"
        )
    return HeldoutSet(
        pairs=pairs,
        source=f"{path}!{HELDOUT_FILENAME}",
        sha256=actual_sha256,
        sha256_verified=True,
        adapter_zip_sha256=_file_sha256(Path(path)),
    )


@dataclass(frozen=True)
class Evaluation:
    total_pairs: int
    skipped: int
    scores: tuple[PairScore, ...]
    base_valid: int
    adapter_valid: int
    identical_replies: bool
    verdict: Verdict
    min_decisive: int
    alpha: float

    @property
    def scoreable(self) -> int:
        return len(self.scores)

    def _count(self, outcome: str) -> int:
        return sum(1 for score in self.scores if score.outcome == outcome)

    @property
    def wins(self) -> int:
        return self._count("win")

    @property
    def losses(self) -> int:
        return self._count("loss")

    @property
    def ties(self) -> int:
        return self._count("tie")

    @property
    def base_valid_rate(self) -> float:
        return self.base_valid / self.scoreable

    @property
    def adapter_valid_rate(self) -> float:
        return self.adapter_valid / self.scoreable

    @property
    def mean_base_error(self) -> float:
        return sum(score.base_error for score in self.scores) / self.scoreable

    @property
    def mean_adapter_error(self) -> float:
        return sum(score.adapter_error for score in self.scores) / self.scoreable

    @property
    def warnings(self) -> list[str]:
        if not self.identical_replies:
            return []
        return [
            "the adapter's replies are identical to the plain model's for every "
            "pair; the adapter may not be applied (check GET /lora-adapters and "
            "try --scale-mode global)"
        ]


def run_evaluation(
    pairs: Sequence[HeldoutPair],
    complete: Callable[[str, float], str],
    *,
    min_decisive: int = DEFAULT_MIN_DECISIVE,
    alpha: float = DEFAULT_ALPHA,
) -> Evaluation:
    """Send every scoreable held-out prompt with the adapter off, then on.

    All "off" requests come first so a server that needs a global scale change
    between the two passes only has to switch once.
    """
    keyed = []
    for pair in pairs:
        key = answer_key(pair.chosen, pair.rejected)
        if key is not None:
            keyed.append((pair, key))
    if not keyed:
        raise ValueError(
            "no held-out pair has a reviewer-changed score in the "
            "criterion_measurements reply shape; nothing to evaluate"
        )
    base_replies = [complete(pair.prompt, 0.0) for pair, _ in keyed]
    adapter_replies = [complete(pair.prompt, 1.0) for pair, _ in keyed]
    base_results = [smoke.validate_sme_reply(text) for text in base_replies]
    adapter_results = [smoke.validate_sme_reply(text) for text in adapter_replies]
    scores = tuple(
        score_pair(
            pair.pair_id,
            key,
            base.scores if base.valid else None,
            adapter.scores if adapter.valid else None,
        )
        for (pair, key), base, adapter in zip(
            keyed, base_results, adapter_results, strict=True
        )
    )
    base_valid = sum(1 for result in base_results if result.valid)
    adapter_valid = sum(1 for result in adapter_results if result.valid)
    wins = sum(1 for score in scores if score.outcome == "win")
    losses = sum(1 for score in scores if score.outcome == "loss")
    verdict = decide(
        wins,
        losses,
        base_valid / len(keyed),
        adapter_valid / len(keyed),
        min_decisive=min_decisive,
        alpha=alpha,
    )
    return Evaluation(
        total_pairs=len(pairs),
        skipped=len(pairs) - len(keyed),
        scores=scores,
        base_valid=base_valid,
        adapter_valid=adapter_valid,
        identical_replies=base_replies == adapter_replies,
        verdict=verdict,
        min_decisive=min_decisive,
        alpha=alpha,
    )


def build_report(
    evaluation: Evaluation,
    *,
    parameters: dict,
    heldout: dict,
    adapter: dict | None,
) -> dict:
    """The JSON report. Holds scores and ids only: never prompts or the API key."""
    return {
        "verdict": evaluation.verdict.verdict,
        "reasons": list(evaluation.verdict.reasons),
        "warnings": evaluation.warnings,
        "pairs": {
            "heldout_total": evaluation.total_pairs,
            "scoreable": evaluation.scoreable,
            "skipped": evaluation.skipped,
            "wins": evaluation.wins,
            "losses": evaluation.losses,
            "ties": evaluation.ties,
        },
        "mean_abs_error": {
            "base": evaluation.mean_base_error,
            "adapter": evaluation.mean_adapter_error,
        },
        "valid_json_rate": {
            "base": evaluation.base_valid_rate,
            "adapter": evaluation.adapter_valid_rate,
        },
        "sign_test_p": evaluation.verdict.p_value,
        "parameters": parameters,
        "heldout": heldout,
        "adapter": adapter,
        "per_pair": [
            {
                "pair_id": score.pair_id,
                "gold": score.gold,
                "base_scores": score.base_scores,
                "adapter_scores": score.adapter_scores,
                "outcome": score.outcome,
            }
            for score in evaluation.scores
        ],
    }


def format_report(evaluation: Evaluation) -> str:
    n = evaluation.scoreable
    header = f"Adapter evaluation: {evaluation.total_pairs} held-out pair(s), {n} scoreable"
    if evaluation.skipped:
        header += f", {evaluation.skipped} skipped (no reviewer-changed score)"
    lines = [
        header,
        "",
        f"  valid JSON       base {evaluation.base_valid}/{n}   "
        f"adapter {evaluation.adapter_valid}/{n}",
        f"  mean abs error   base {evaluation.mean_base_error:.3f}   "
        f"adapter {evaluation.mean_adapter_error:.3f}",
        f"  per pair         adapter {evaluation.wins} win(s), "
        f"{evaluation.losses} loss(es), {evaluation.ties} tie(s); "
        f"sign test p={evaluation.verdict.p_value:.4f}",
        "",
        f"VERDICT: {evaluation.verdict.verdict.upper()}",
    ]
    lines.extend(f"  - {reason}" for reason in evaluation.verdict.reasons)
    lines.extend(f"WARNING: {warning}" for warning in evaluation.warnings)
    lines.extend(["", LIMITS_NOTE])
    return "\n".join(lines)


def exit_code(evaluation: Evaluation) -> int:
    return 0 if evaluation.verdict.verdict == "better" else 1


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare a GGUF LoRA adapter with the plain model on held-out "
        "DPO pairs."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--adapter-zip",
        type=Path,
        help="adapter zip from the training notebook (holds heldout_pairs.jsonl)",
    )
    source.add_argument(
        "--heldout", type=Path, help="a bare heldout_pairs.jsonl file instead"
    )
    parser.add_argument("--base-url", default=None, help="default: $LLM_API_BASE")
    parser.add_argument("--api-key", default=None, help="default: $LLM_API_KEY")
    parser.add_argument("--model", default=None, help="default: $LLM_MODEL_NAME")
    parser.add_argument(
        "--adapter-id",
        type=int,
        default=None,
        help="adapter id to evaluate (default: the first loaded adapter)",
    )
    parser.add_argument(
        "--scale-mode",
        choices=("request", "global"),
        default="request",
        help="request: send the scale in each chat request (default). global: "
        "set it through POST /lora-adapters; this changes the server-wide "
        "scale, and the script resets it to 0.0 afterwards",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=f"max tokens per reply (default: {DEFAULT_MAX_TOKENS})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="seconds to wait for each HTTP request (default: 300)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="evaluate only the first N held-out pairs (default: all)",
    )
    parser.add_argument(
        "--min-decisive",
        type=int,
        default=DEFAULT_MIN_DECISIVE,
        help="fewest decisive (win or loss) pairs for a verdict other than "
        f"inconclusive (default: {DEFAULT_MIN_DECISIVE})",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=DEFAULT_ALPHA,
        help=f"significance level of the sign test (default: {DEFAULT_ALPHA})",
    )
    parser.add_argument(
        "--report-json", type=Path, default=None, help="also write a JSON report here"
    )
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.min_decisive < 1:
        parser.error("--min-decisive must be at least 1")
    if not 0 < args.alpha < 1:
        parser.error("--alpha must be between 0 and 1")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    base_url = args.base_url or os.environ.get("LLM_API_BASE")
    if not base_url:
        print(
            "error: no server base URL; pass --base-url or set LLM_API_BASE",
            file=sys.stderr,
        )
        return 2
    api_key = args.api_key or os.environ.get("LLM_API_KEY")
    model = args.model or os.environ.get("LLM_MODEL_NAME") or smoke.DEFAULT_MODEL
    adapter_id: int | None = None
    scale_touched: list[bool] = []
    try:
        try:
            if args.adapter_zip:
                heldout = load_heldout_zip(args.adapter_zip)
            else:
                heldout = load_heldout_file(args.heldout)
            pairs = heldout.pairs[: args.limit] if args.limit else heldout.pairs
            adapters = smoke.list_adapters(base_url, api_key, args.timeout)
            adapter_id = smoke.choose_adapter_id(adapters, args.adapter_id)
            complete = smoke.make_complete(
                base_url=base_url,
                api_key=api_key,
                model=model,
                adapter_id=adapter_id,
                scale_mode=args.scale_mode,
                max_tokens=args.max_tokens,
                timeout=args.timeout,
                scale_touched=scale_touched,
            )
            evaluation = run_evaluation(
                pairs, complete, min_decisive=args.min_decisive, alpha=args.alpha
            )
        except (
            OSError,
            ValueError,
            http.client.HTTPException,
            zipfile.BadZipFile,
        ) as exc:
            print(f"error: {smoke.describe_error(exc)}", file=sys.stderr)
            return 2
        checked = "verified" if heldout.sha256_verified else "not checked"
        print(
            f"Held-out set: {heldout.source} ({len(pairs)} of "
            f"{len(heldout.pairs)} pair(s) used, sha256 {checked})"
        )
        print(format_report(evaluation))
        if args.report_json:
            report = build_report(
                evaluation,
                parameters={
                    "min_decisive": args.min_decisive,
                    "alpha": args.alpha,
                    "scale_mode": args.scale_mode,
                    "model": model,
                    "max_tokens": args.max_tokens,
                    "limit": args.limit,
                },
                heldout={
                    "source": heldout.source,
                    "sha256": heldout.sha256,
                    "sha256_verified": heldout.sha256_verified,
                    "pairs_in_file": len(heldout.pairs),
                    "pairs_used": len(pairs),
                },
                adapter={
                    "adapter_id": adapter_id,
                    "zip_sha256": heldout.adapter_zip_sha256,
                },
            )
            try:
                args.report_json.write_text(
                    json.dumps(report, indent=2) + "\n", encoding="utf-8"
                )
            except OSError as exc:
                print(f"error: could not write the report: {exc}", file=sys.stderr)
                return 2
            print(f"report written to {args.report_json}")
        return exit_code(evaluation)
    finally:
        if args.scale_mode == "global" and scale_touched and adapter_id is not None:
            smoke.reset_global_scale(base_url, api_key, adapter_id, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
