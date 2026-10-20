"""Code-owned metadata agreement, reconstructed only from frozen durable evidence.

These are located field agreements, NOT originality, claim truth, ownership or
permission findings. Candidate inventories do not establish bibliography coverage.
"""

from __future__ import annotations

import hashlib
import json
import re
from functools import wraps
from uuid import UUID

from equiped_harness.itso.history_contracts import EvidenceFact, SourceSpan
from server.modules.documents.source_artifacts import DocumentSourceSnapshot
from sqlalchemy import select

from .attachment_context import attachment_scope_hash, frozen_attachment_contexts
from .exceptions import ITSOError
from .policy_service import checked_policy, digest
from .tool_models import ToolAttempt, VerificationRun, VerificationTask
from .verification import ToolCapture, VerificationPlan
from .verification.providers import brave_url, doi_url, match_metadata, normalize
from .workflow_models import AssessmentEvidence, PreflightAuthorization


def _integrity_guard(function):
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (ValueError, KeyError, TypeError):
            raise ITSOError("assessment_integrity_failed") from None

    return checked


@_integrity_guard
def frozen_scope(db, parent, source):
    auth = db.scalar(
        select(PreflightAuthorization).where(
            PreflightAuthorization.consumed_evaluation_id == parent.evaluation_id
        )
    )
    if auth is None or digest(auth.manifest) != auth.manifest_hash:
        raise ITSOError("assessment_integrity_failed")
    plan = VerificationPlan.model_validate(auth.manifest["plan"])
    disclosure = auth.manifest["disclosure"]
    artifact = db.get(DocumentSourceSnapshot, parent.source_snapshot_id)
    if (
        artifact is None
        or disclosure["inventory_hash"] != artifact.inventory_hash
        or auth.actor_id != parent.owner_id
        or auth.document_id != parent.document_id
        or auth.source_snapshot_id != parent.source_snapshot_id
        or auth.source_hash != source.source_hash
        or parent.source_hash != source.source_hash
        or auth.reservation != plan.reservation
        or disclosure["profile"] != plan.profile.model_dump(mode="json")
        or auth.effective_policy_hash != parent.effective_policy_hash
        or plan.source_snapshot_hash != source.source_hash
        or plan.disclosure_hash != digest(disclosure)
        or disclosure["actor_id"] != str(parent.owner_id)
        or disclosure["document_id"] != str(parent.document_id)
        or disclosure["source_snapshot_id"] != str(parent.source_snapshot_id)
        or disclosure["source_hash"] != source.source_hash
        or disclosure["raw_pdf_hash"] != source.raw_pdf_hash
        or disclosure["effective_policy_hash"] != parent.effective_policy_hash
        or disclosure["external_verification"] != auth.external_verification
        or disclosure["references"]
        != [t.model_dump(mode="json") for t in plan.references]
        or disclosure["pages"] != [t.model_dump(mode="json") for t in plan.pages]
        or disclosure["policy_versions"] != auth.policy_versions
        or disclosure["inventory_count"] != len(source.references)
    ):
        raise ITSOError("assessment_integrity_failed")
    policies = [checked_policy(db, UUID(version)) for version in auth.policy_versions]
    policy_hash = digest(
        [
            {"version_id": str(p.policy_version_id), "payload_hash": p.payload_hash}
            for p in policies
        ]
    )
    if (
        attachment_scope_hash(policy_hash, disclosure["attachments"])
        != parent.effective_policy_hash
    ):
        raise ITSOError("assessment_integrity_failed")
    frozen_attachment_contexts(db, auth)
    return auth, plan


@_integrity_guard
def ledger_fingerprint(db, parent, source):
    """Seal all provenance, including unsuccessful requests and unstarted lanes."""
    auth, plan = frozen_scope(db, parent, source)
    run = db.get(VerificationRun, plan.plan_hash)
    tasks = list(
        db.scalars(
            select(VerificationTask)
            .where(VerificationTask.plan_hash == plan.plan_hash)
            .order_by(VerificationTask.task_id)
        )
    )
    attempts = list(
        db.scalars(
            select(ToolAttempt)
            .where(ToolAttempt.plan_hash == plan.plan_hash)
            .order_by(ToolAttempt.task_id, ToolAttempt.ordinal)
        )
    )
    if run is not None and (
        run.assessment_id != parent.assessment_id
        or run.plan_payload != plan.model_dump(mode="json")
        or run.reservation != plan.reservation
        or run.attempt_count != len(attempts)
        or {t.task_id for t in tasks}
        != {t.task_id for t in (*plan.references, *plan.pages)}
    ):
        raise ITSOError("assessment_integrity_failed")
    if (not auth.external_verification and run is not None) or (
        run is None and (tasks or attempts)
    ):
        raise ITSOError("assessment_integrity_failed")
    for task in tasks:
        lane = [a for a in attempts if a.task_id == task.task_id]
        if task.attempt_count != len(lane) or [a.ordinal for a in lane] != list(
            range(1, len(lane) + 1)
        ):
            raise ITSOError("assessment_integrity_failed")

    def data(row):
        return {
            column.name: (str(value) if isinstance(value, UUID) else value)
            for column in row.__table__.columns
            for value in (getattr(row, column.name),)
        }

    provenance = {
        "manifest_hash": auth.manifest_hash,
        "run": data(run) if run else None,
        "tasks": [data(t) for t in tasks],
        "attempts": [data(a) for a in attempts],
    }
    # Preserve existing sealed no-attachment histories byte-for-byte. New active
    # attachments do not become part of an earlier assessment's frozen scope.
    if auth.manifest["disclosure"]["attachments"]:
        provenance["attachments"] = frozen_attachment_contexts(db, auth)
    return digest(provenance)


@_integrity_guard
def recompute_facts(db, parent, source):
    """Never accept authority or matching assertions from result/model JSON."""
    auth, plan = frozen_scope(db, parent, source)
    fingerprint = ledger_fingerprint(db, parent, source)
    if not auth.external_verification:
        return ()
    if {"verification_seal": fingerprint} not in list(
        db.scalars(
            select(AssessmentEvidence.payload).where(
                AssessmentEvidence.assessment_id == parent.assessment_id
            )
        )
    ):
        raise ITSOError("assessment_integrity_failed")
    facts = []
    exact_references = {}
    references = {r.reference_id: r for r in source.references}
    for task in plan.references:
        ref = task.reference
        candidate = references.get(ref.source_id)
        if candidate is None:
            raise ITSOError("assessment_integrity_failed")
        quote = source.canonical_text[candidate.start_offset : candidate.end_offset]
        # Recheck the exact approved occurrence, not any other place in the SLM.
        fields = [
            v
            for v in (ref.title, *ref.authors, str(ref.year) if ref.year else None)
            if v
        ]
        normalized = " " + normalize(quote) + " "
        if any(" " + normalize(v) + " " not in normalized for v in fields) or (
            ref.doi
            and not re.search(
                r"(?<![a-z0-9])"
                + re.escape(ref.doi.casefold())
                + r"(?![a-z0-9._;()/:+\-])",
                quote.casefold(),
            )
        ):
            raise ITSOError("assessment_integrity_failed")
        row = db.get(VerificationTask, (plan.plan_hash, task.task_id))
        if row is None or row.capture_payload is None:
            continue  # readiness failure or a later lane never started
        capture = ToolCapture.model_validate(row.capture_payload)
        attempts = list(
            db.scalars(
                select(ToolAttempt)
                .where(
                    ToolAttempt.plan_hash == plan.plan_hash,
                    ToolAttempt.task_id == task.task_id,
                )
                .order_by(ToolAttempt.ordinal)
            )
        )
        if (
            not row.started
            or capture.task_id != task.task_id
            or capture.plan_hash != plan.plan_hash
            or capture.source_snapshot_hash != source.source_hash
            or capture.reference_hash != ref.reference_hash
            or capture.attempt_count != len(attempts)
        ):
            raise ITSOError("assessment_integrity_failed")
        for attempt in attempts:
            url = (
                doi_url(attempt.request_class, ref.doi)
                if task.kind == "doi"
                and attempt.request_class in {"crossref", "datacite"}
                else brave_url(ref)
                if task.kind == "search" and attempt.request_class == "brave"
                else None
            )
            if url is None or attempt.destination_hash != digest_url(url):
                raise ITSOError("assessment_integrity_failed")
        if capture.status in {"unavailable", "execution_error"}:
            continue
        if not attempts or any(not a.completed for a in attempts):
            raise ITSOError("assessment_integrity_failed")
        last = attempts[-1]
        url = (
            doi_url(capture.provider, ref.doi)
            if task.kind == "doi" and capture.provider in {"crossref", "datacite"}
            else brave_url(ref)
            if task.kind == "search" and capture.provider == "brave"
            else None
        )
        if (
            url is None
            or last.request_class != capture.provider
            or last.destination_hash != digest_url(url)
            or capture.request_sha256 != last.destination_hash
            or capture.http_status != last.http_status
            or last.error_code is not None
            or not capture.content_sha256
            or (
                capture.provider == "datacite"
                and not any(
                    a.request_class == "crossref"
                    and a.http_status == 404
                    and a.completed
                    and a.error_code is None
                    for a in attempts[:-1]
                )
            )
        ):
            raise ITSOError("assessment_integrity_failed")
        if capture.status == "not_found_registry":
            if (
                capture.provider != "datacite"
                or last.http_status != 404
                or capture.metadata is not None
            ):
                raise ITSOError("assessment_integrity_failed")
            continue  # Registry absence is not absence of a work or citation.
        if task.kind != "doi":
            continue  # Search/page labels do not supply parsed bibliographic identity.
        if (
            last.http_status != 200
            or capture.metadata is None
            or capture.reason is not None
        ):
            raise ITSOError("assessment_integrity_failed")
        status, matched, mismatched = match_metadata(ref, capture.metadata)
        if (capture.status, capture.matched_fields, capture.mismatched_fields) != (
            status,
            matched,
            mismatched,
        ):
            raise ITSOError("assessment_integrity_failed")
        if status != "matched":
            continue  # Ambiguity never supplies a positive identity claim.
        span = SourceSpan(
            source_id=source.source_id,
            start_offset=candidate.start_offset,
            end_offset=candidate.end_offset,
            text_hash=candidate.text_hash,
        )
        scope = {
            "scope": (
                "approved bibliography occurrence / public metadata field agreement "
                "only; not originality, claim truth or permission"
            ),
            "reference_id": ref.source_id,
            "reference_hash": ref.reference_hash,
            "plan_hash": plan.plan_hash,
            "task_id": task.task_id,
            "provider": capture.provider,
            "capture_hash": digest(capture.model_dump(mode="json")),
        }
        exact_fields = set()
        for field, method in (
            ("title", "exact-title.v1"),
            ("author", "exact-author.v1"),
            ("year", "exact-year.v1"),
            ("doi", "citation-link.v1"),
        ):
            if field not in matched:
                continue
            if field == "author" and {normalize(a) for a in ref.authors} != {
                normalize(a) for a in capture.metadata.authors
            }:
                continue
            if field == "year" and set(capture.metadata.years) != {ref.year}:
                continue
            exact_fields.add(field)
            value = dict(scope, field=field, agreement=True)
            facts.append(
                EvidenceFact(
                    fact_id="metadata:"
                    + digest(
                        {"task": task.task_id, "field": field, "plan": plan.plan_hash}
                    ),
                    predicate="public_metadata_agreement." + field,
                    value=json.dumps(value, sort_keys=True, separators=(",", ":")),
                    authority="verified_mechanical",
                    source_spans=(span,),
                    origin="durable_public_metadata",
                    method_version=method,
                )
            )
        if exact_fields == {"title", "author", "year", "doi"}:
            exact_references[ref.source_id] = span
    # identity_intact means the FULL frozen bibliography's four identity fields
    # agree, not that one selected reference matches. The durable regex inventory
    # is explicitly incomplete, so it cannot enter this affirmative branch.
    if (
        source.inventory_complete
        and references
        and set(exact_references) == set(references)
        and len(plan.references) == len(references)
    ):
        for version in auth.policy_versions:
            policy = checked_policy(db, UUID(version))
            if policy.kind != "rule" or policy.criterion_id != "ITSO-02":
                continue
            facts.append(
                EvidenceFact(
                    fact_id="identity:"
                    + digest({"plan": plan.plan_hash, "policy": version}),
                    predicate="approved_reference_format_defect_identity_intact.identity_intact",
                    value="true",
                    authority="verified_mechanical",
                    source_spans=tuple(
                        exact_references[key] for key in sorted(references)
                    ),
                    origin="complete_bibliography_metadata_identity",
                    method_version="hash-offset.v1",
                    policy_version=version,
                )
            )
    # No supported_check_results, contradiction, missing-link or citation-absence
    # input is inferred: metadata agreement alone cannot resolve those checks.
    return (("ITSO-02", tuple(facts)),) if facts else ()


def digest_url(url):
    return hashlib.sha256(url.encode()).hexdigest()
