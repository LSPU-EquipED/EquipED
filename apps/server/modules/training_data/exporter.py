"""Unified DPO training package exporter."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from server.modules.feedback.models import PreferenceLog
from server.modules.feedback.state import get_effective_criterion_corrections_batch
from server.modules.rubrics.snapshots import load_verified_agent_snapshot
from server.modules.synthesis.models import AgentGeneration
from server.modules.training_data.capabilities import get_contract_capability
from server.modules.training_data.contracts import DpoPackageManifest, DpoPair
from server.modules.training_data.projectors import (
    ProjectionResult,
    project_criterion_measurements_v1,
    project_gad_extraction_v1,
    project_itso_scores_v1,
)
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_ITEM_LEVEL_ACTIONS = ("ITEM_REJECT", "ITEM_ACCEPT")


def _effective_rejections_with_reviewers_for_evaluations(
    session: Session, evaluation_ids: Sequence[uuid.UUID], agent_id: str
) -> dict[uuid.UUID, dict[str, tuple[frozenset[str], frozenset[uuid.UUID]]]]:
    """Return {evaluation_id: {criterion_id: (rejected_item_ids, reviewer_ids)}}."""
    if not evaluation_ids:
        return {}

    logs: list[PreferenceLog] = (
        session.query(PreferenceLog)
        .filter(
            PreferenceLog.evaluation_id.in_(evaluation_ids),
            PreferenceLog.agent_name == agent_id,
            PreferenceLog.action.in_(_ITEM_LEVEL_ACTIONS),
            PreferenceLog.item_id.isnot(None),
        )
        .order_by(PreferenceLog.created_at.desc(), PreferenceLog.log_id.desc())
        .all()
    )

    latest_by_key: dict[tuple[uuid.UUID, str, str], PreferenceLog] = {}
    for log in logs:
        if not log.criterion_id or not log.item_id:
            continue
        key = (log.evaluation_id, log.criterion_id, log.item_id)
        if key not in latest_by_key:
            latest_by_key[key] = log

    rejected_items: dict[uuid.UUID, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    reviewers: dict[uuid.UUID, dict[str, set[uuid.UUID]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for (eval_id, criterion_id, item_id), log in latest_by_key.items():
        if log.action == "ITEM_REJECT":
            rejected_items[eval_id][criterion_id].add(item_id)
            if log.user_id:
                reviewers[eval_id][criterion_id].add(log.user_id)

    result: dict[uuid.UUID, dict[str, tuple[frozenset[str], frozenset[uuid.UUID]]]] = {}
    for eval_id, criteria in rejected_items.items():
        result[eval_id] = {
            cid: (frozenset(items), frozenset(reviewers[eval_id][cid]))
            for cid, items in criteria.items()
        }
    return result


def export_dpo_package(
    session: Session,
    agent_id: str,
    output_dir: Path,
    *,
    model_name: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    dry_run: bool = False,
) -> DpoPackageManifest:
    """Export a unified DPO package containing pairs, provenance, and manifest.

    Atomically writes to output_dir using a temp folder and atomic rename unless
    dry_run is True.
    """
    query = (
        session.query(AgentGeneration)
        .filter(
            AgentGeneration.agent_id == agent_id,
            AgentGeneration.envelope_status == "ok",
        )
        .order_by(AgentGeneration.created_at.asc(), AgentGeneration.generation_id.asc())
    )

    if model_name:
        query = query.filter(AgentGeneration.model_name == model_name)
    if since:
        query = query.filter(AgentGeneration.created_at >= since)
    if until:
        query = query.filter(AgentGeneration.created_at <= until)

    generations: list[AgentGeneration] = query.all()

    # Pre-fetch corrections and item rejections for all candidate evaluations
    eval_ids = list({g.evaluation_id for g in generations})
    corrections_by_eval = get_effective_criterion_corrections_batch(
        session, eval_ids, agent_names=[agent_id]
    )
    rejections_by_eval = _effective_rejections_with_reviewers_for_evaluations(
        session, eval_ids, agent_id
    )

    pairs: list[DpoPair] = []
    provenance_records: list[dict] = []
    skipped_counts: dict[str, int] = defaultdict(int)
    response_contract_keys: set[str] = set()
    evaluation_ids_used: set[uuid.UUID] = set()
    reviewer_ids_used: set[uuid.UUID] = set()

    for gen in generations:
        contract_key = gen.response_contract_key
        version = gen.response_contract_version
        response_contract_keys.add(contract_key)
        capability = get_contract_capability(contract_key, version)

        # Validate snapshot integrity before projecting
        try:
            load_verified_agent_snapshot(session, gen.evaluation_id, gen.agent_id)
        except Exception as exc:
            logger.warning(
                "Snapshot verification failed for evaluation %s agent %s: %s",
                gen.evaluation_id,
                gen.agent_id,
                exc,
            )
            skipped_counts["snapshot_verification_failed"] += 1
            continue

        if capability.skip_reason:
            skipped_counts[capability.skip_reason] += 1
            continue

        eval_corrections = corrections_by_eval.get(gen.evaluation_id, {})
        # Map (agent_id, criterion_id) -> criterion_id
        corr_for_agent = {
            cid: corr
            for (a, cid), corr in eval_corrections.items()
            if a == gen.agent_id and cid in gen.criterion_ids
        }
        rejections_for_eval = rejections_by_eval.get(gen.evaluation_id, {})
        rej_for_agent = {
            cid: entry
            for cid, entry in rejections_for_eval.items()
            if cid in gen.criterion_ids
        }

        # Check if this generation had any corrections or rejections at all
        if not corr_for_agent and not rej_for_agent:
            skipped_counts["no_reviewer_feedback"] += 1
            continue

        proj_result: ProjectionResult
        if contract_key == "criterion_measurements.v1" and version == 1:
            proj_result = project_criterion_measurements_v1(
                gen, corr_for_agent, rej_for_agent
            )
        elif contract_key == "itso_scores.v1" and version == 1:
            proj_result = project_itso_scores_v1(gen, corr_for_agent)
        elif contract_key == "gad_extraction.v1" and version == 1:
            proj_result = project_gad_extraction_v1(gen, corr_for_agent)
        else:
            proj_result = ProjectionResult(
                skip_reason=f"unhandled_contract_{contract_key}_v{version}"
            )

        if proj_result.skip_reason:
            skipped_counts[proj_result.skip_reason] += 1
            continue

        if proj_result.pair is not None:
            pair = proj_result.pair
            pairs.append(pair)
            evaluation_ids_used.add(pair.evaluation_id)
            reviewer_ids_used.update(pair.reviewer_ids)

            prov_record = {
                "pair_id": pair.pair_id,
                "generation_id": str(pair.generation_id),
                "evaluation_id": str(pair.evaluation_id),
                "document_id": str(pair.document_id),
                "agent_id": pair.agent_id,
                "unit_key": gen.unit_key,
                "model_name": pair.model_name,
                "response_contract_key": gen.response_contract_key,
                "response_contract_version": gen.response_contract_version,
                "criterion_ids": gen.criterion_ids,
                "reviewer_ids": [str(rid) for rid in sorted(pair.reviewer_ids)],
                "prompt_sha256": gen.prompt_sha256,
                "response_sha256": gen.response_sha256,
                "created_at": gen.created_at.isoformat() if gen.created_at else None,
            }
            provenance_records.append(prov_record)

    # Render pairs.jsonl and provenance.jsonl in memory
    pairs_lines = [
        json.dumps(
            {
                "prompt": p.prompt,
                "chosen": p.chosen,
                "rejected": p.rejected,
            },
            ensure_ascii=False,
        )
        + "\n"
        for p in pairs
    ]
    pairs_content = "".join(pairs_lines).encode("utf-8")
    pairs_sha256 = hashlib.sha256(pairs_content).hexdigest()
    pairs_bytes = len(pairs_content)

    prov_lines = [json.dumps(r, ensure_ascii=False) + "\n" for r in provenance_records]
    prov_content = "".join(prov_lines).encode("utf-8")
    prov_sha256 = hashlib.sha256(prov_content).hexdigest()
    prov_bytes = len(prov_content)

    export_timestamp = datetime.now(UTC).isoformat()
    manifest = DpoPackageManifest(
        manifest_version="equiped.dpo-package.v1",
        agent_id=agent_id,
        model_name=model_name,
        response_contract_keys=sorted(response_contract_keys),
        pair_count=len(pairs),
        evaluation_count=len(evaluation_ids_used),
        reviewer_count=len(reviewer_ids_used),
        skipped_counts=dict(sorted(skipped_counts.items())),
        pairs_sha256=pairs_sha256,
        pairs_bytes=pairs_bytes,
        provenance_sha256=prov_sha256,
        provenance_bytes=prov_bytes,
        export_timestamp=export_timestamp,
    )

    if dry_run:
        return manifest

    # Write files atomically using a temp directory next to or within output_dir parent
    output_dir = output_dir.resolve()
    parent_dir = output_dir.parent
    parent_dir.mkdir(parents=True, exist_ok=True)

    tmp_dir = tempfile.mkdtemp(prefix=".dpo_export_tmp_", dir=parent_dir)
    tmp_path = Path(tmp_dir)
    try:
        pairs_file = tmp_path / "pairs.jsonl"
        with pairs_file.open("wb") as f:
            f.write(pairs_content)
            f.flush()
            os.fsync(f.fileno())

        prov_file = tmp_path / "provenance.jsonl"
        with prov_file.open("wb") as f:
            f.write(prov_content)
            f.flush()
            os.fsync(f.fileno())

        manifest_file = tmp_path / "manifest.json"
        manifest_bytes = manifest.model_dump_json(indent=2).encode("utf-8")
        with manifest_file.open("wb") as f:
            f.write(manifest_bytes)
            f.flush()
            os.fsync(f.fileno())

        # If output_dir already exists, replace it safely with rollback
        if output_dir.exists():
            backup_dir = tempfile.mkdtemp(prefix=".dpo_export_bak_", dir=parent_dir)
            Path(backup_dir).rmdir()
            output_dir.rename(backup_dir)
            try:
                tmp_path.rename(output_dir)
                shutil.rmtree(backup_dir, ignore_errors=True)
            except Exception:
                Path(backup_dir).rename(output_dir)
                raise
        else:
            tmp_path.rename(output_dir)
    except Exception:
        shutil.rmtree(tmp_path, ignore_errors=True)
        raise

    return manifest


__all__ = [
    "export_dpo_package",
]
