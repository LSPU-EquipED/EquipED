"""Current Coordinator orchestration; historical contracts live in legacy.py."""

from __future__ import annotations

import json
import time
from typing import Any

from equiped_harness.agents.coordinator.catalog import _catalog
from equiped_harness.agents.coordinator.contracts import (
    CoordinatorAlignmentAdvisory,
    CurriculumObjectiveMatch,
)
from equiped_harness.agents.coordinator.legacy import replay_client, run_legacy
from equiped_harness.agents.coordinator.measurements import (
    _score_ordinary,
    _validate_objective,
)
from equiped_harness.agents.coordinator.source_inventory import resolve_inventory
from equiped_harness.agents.coordinator.task_execution import _call_task
from equiped_harness.agents.coordinator.task_prompts import (
    _canonical_ordinary_example,
    _Task,
    _task_prompt,
)
from equiped_harness.contracts.results import (
    AgentEvaluationResult,
    CapturedGeneration,
    CriterionScore,
)
from equiped_harness.exceptions import AgentExecutionError
from equiped_harness.runtime.bands import ratio_band
from equiped_harness.runtime.config import current_execution_config
from equiped_harness.runtime.llm import RunLLMClient

CONTRACT = "coordinator_current.v1"
_MAX_TASKS = 32
_CURRENT_REPAIR_BUDGET_CHARS = 1_200
_CURRENT_RESPONSE_BUDGETS = {"ordinary": 512, "objective": 1_024, "curriculum": 1_024}


def run_current(
    coordinator: Any,
    *,
    evaluation_id: Any,
    document_id: Any,
    form_snapshot: Any,
    chunk_infos: list[dict[str, Any]],
    canonical_source_text: str | None,
    curriculum_id: Any,
    curriculum_context: str | None,
    reference_document_ids: dict[str, Any] | None,
    prompt_version_id: Any,
    roadmap_context: dict[str, Any] | None,
    llm_client: Any | None,
    **kwargs: Any,
) -> AgentEvaluationResult:
    del kwargs, roadmap_context
    from equiped_harness.contracts.snapshots import EvaluationFormSnapshotDTO
    from equiped_harness.manifests import get_agent_manifest, validate_form

    if (
        not isinstance(form_snapshot, EvaluationFormSnapshotDTO)
        or form_snapshot.agent_id != "coordinator"
        or form_snapshot.evaluation_id != evaluation_id
    ):
        raise AgentExecutionError("Coordinator snapshot binding is invalid")
    if form_snapshot.adapter_version != 3:
        return run_legacy(
            coordinator,
            evaluation_id=evaluation_id,
            document_id=document_id,
            form_snapshot=form_snapshot,
            chunk_infos=chunk_infos,
            canonical_source_text=canonical_source_text,
            curriculum_id=curriculum_id,
            curriculum_context=curriculum_context,
            reference_document_ids=reference_document_ids,
            prompt_version_id=prompt_version_id,
            llm_client=llm_client,
        )
    report = validate_form(form_snapshot.form, get_agent_manifest("coordinator", 3))
    if not report.is_valid:
        raise AgentExecutionError(
            "Coordinator snapshot violates current adapter contract"
        )
    if not canonical_source_text or not canonical_source_text.strip():
        raise AgentExecutionError("canonical source text is required")
    if not chunk_infos:
        raise AgentExecutionError("document chunks are required for evaluation")
    if (
        not curriculum_id
        or not isinstance(curriculum_context, str)
        or not curriculum_context.strip()
    ):
        raise AgentExecutionError(
            "Coordinator requires curriculum_id and authoritative curriculum context"
        )
    client = llm_client or coordinator._default_llm_client
    if client is None:
        raise AgentExecutionError("Coordinator requires an assigned LLM client")
    started = time.perf_counter()
    adapter = (
        client
        if isinstance(client, RunLLMClient)
        else RunLLMClient(
            client, "coordinator", requested_model=getattr(client, "model", "unknown")
        )
    )
    settings = current_execution_config()
    deadline = time.monotonic() + float(settings.llm_request_timeout_seconds)
    resolution = resolve_inventory(canonical_source_text, adapter, deadline=deadline)
    inventory = resolution.inventory
    catalog = _catalog(canonical_source_text, inventory, curriculum_context.strip())
    criteria = tuple(c for d in form_snapshot.form.domains for c in d.criteria)
    task_specs = [
        (f"ordinary-{c.criterion_code}", "ordinary", (c,))
        for c in criteria
        if (c.criterion_code.startswith("OP-") or c.criterion_code.startswith("A-"))
        and c.criterion_code != "A-05"
    ]
    reserved_tasks = 1 + int(bool(inventory.assessment_sections))
    if len(task_specs) + reserved_tasks > _MAX_TASKS:
        raise AgentExecutionError("Coordinator task capacity exceeded")
    if inventory.assessment_sections:
        task_specs.append(("objective-assessment", "objective", ()))
    task_specs.append(("curriculum", "curriculum", ()))
    objectives = tuple(
        {"objective_id": o.objective_id, "text": o.text} for o in inventory.objectives
    )
    tasks = [
        _Task(
            task_id,
            kind,
            task_criteria,
            _task_prompt(
                task_id, task_criteria, catalog, kind=kind, objectives=objectives
            ),
        )
        for task_id, kind, task_criteria in task_specs
    ]
    if any(
        len(task.prompt) + _CURRENT_REPAIR_BUDGET_CHARS
        > settings.agent_total_prompt_budget_chars
        for task in tasks
    ):
        raise AgentExecutionError(
            "Coordinator prompt or repair budget exceeded before model calls"
        )
    scores: list[CriterionScore] = []
    facts: dict[str, Any] = {
        "criteria": {},
        "objective": {
            "assessment_available": bool(inventory.assessment_sections),
            "rows": [],
        },
        "curriculum": {"rows": []},
        "catalog": [v.as_dict() for v in catalog.values()],
    }
    generations = list(resolution.generations)
    repaired_any = any(g.envelope_status == "repaired" for g in generations)
    for index, task in enumerate(tasks):
        task_id, kind, prompt = task.task_id, task.kind, task.prompt
        task_criteria = task.criteria

        def validate_task(data: dict[str, Any]) -> None:
            if kind == "ordinary":
                if len(task_criteria) != 1:
                    raise AgentExecutionError(
                        "Current Coordinator ordinary task must contain one criterion"
                    )
                if len(data["results"]) != 1:
                    raise AgentExecutionError(
                        "Current Coordinator ordinary task row count mismatch"
                    )
                for criterion, row in zip(task_criteria, data["results"], strict=True):
                    _score_ordinary(criterion, row, catalog)
            elif kind == "objective":
                _validate_objective(data, inventory, catalog, dimension="assessment")
            else:
                _validate_objective(data, inventory, catalog, dimension="curriculum")

        if kind == "ordinary":
            example, _ = _canonical_ordinary_example(task_criteria[0].strategy_config)
            repair_instruction = (
                "Repair contract: emit exactly this one-row shape, with no "
                f"criteria key or extra fields: {example} "
                "The status and values in this example are illustrative only."
            )
        else:
            repair_instruction = (
                f"Repair contract: emit exactly {len(inventory.objectives)} results "
                "rows, one for every objective_id in the RUBRIC and in that order. "
                "Each row must contain exactly objective_id and source_ids; emit no "
                "criteria key or extra fields. Use source_ids=[] when unsupported."
            )
        parsed, repaired, completion = _call_task(
            prompt,
            adapter,
            deadline=deadline,
            validator=validate_task,
            response_budget=_CURRENT_RESPONSE_BUDGETS[kind],
            repair_instruction=repair_instruction,
            allow_bare_results=kind in {"objective", "curriculum"},
        )
        # A legacy fake/persisted transport is replayed through the old validator.
        if index == 0 and set(parsed) == {"summary", "criterion_measurements"}:
            return run_legacy(
                coordinator,
                evaluation_id=evaluation_id,
                document_id=document_id,
                form_snapshot=form_snapshot,
                chunk_infos=chunk_infos,
                canonical_source_text=canonical_source_text,
                curriculum_id=curriculum_id,
                curriculum_context=curriculum_context,
                reference_document_ids={"curriculum": curriculum_id},
                prompt_version_id=prompt_version_id,
                llm_client=replay_client(completion, adapter),
            )
        repaired_any = repaired_any or repaired
        generation_criteria = tuple(c.criterion_code for c in task_criteria)
        if not generation_criteria:
            # CapturedGeneration requires an official snapshot criterion.  The
            # curriculum task is a separate advisory task, but C-01 is not an
            # official snapshot criterion, so retain A-05 as its replay anchor.
            generation_criteria = ("A-05",)
        generations.append(
            CapturedGeneration(
                task_id,
                generation_criteria,
                prompt.render_flat(),
                tuple({"role": m.role, "content": m.content} for m in prompt.messages),
                json.dumps(parsed, ensure_ascii=False),
                parsed,
                f"coordinator_current_{kind}.v1",
                1,
                adapter.model,
                "repaired" if repaired else "ok",
            )
        )
        if kind == "ordinary":
            if len(parsed["results"]) != len(task_criteria):
                raise AgentExecutionError("Current Coordinator task row count mismatch")
            for c, row in zip(task_criteria, parsed["results"], strict=True):
                if not isinstance(row, dict):
                    raise AgentExecutionError(
                        "Current Coordinator row must be an object"
                    )
                score, fact = _score_ordinary(c, row, catalog)
                scores.append(score)
                facts["criteria"][c.criterion_code] = fact
        elif kind == "objective":
            rows = _validate_objective(
                parsed, inventory, catalog, dimension="assessment"
            )
            facts["objective"]["rows"] = rows
        else:
            rows = _validate_objective(
                parsed, inventory, catalog, dimension="curriculum"
            )
            facts["curriculum"]["rows"] = rows
    if not inventory.assessment_sections:
        facts["objective"]["rows"] = [
            {"objective_id": o.objective_id, "source_ids": []}
            for o in inventory.objectives
        ]
        a05 = next((c for c in criteria if c.criterion_code == "A-05"), None)
        if a05 is not None:
            scores.append(
                CriterionScore(
                    "A-05",
                    a05.title,
                    1,
                    "Objective gauging: no assessment sections found; "
                    "deterministic score 1.",
                    evidence=(),
                )
            )
    else:
        rows = facts["objective"]["rows"]
        matched = sum(bool(r["source_ids"]) for r in rows)
        pct = matched / len(rows) * 100
        a05 = next((c for c in criteria if c.criterion_code == "A-05"), None)
        if a05 is not None:
            score = ratio_band(matched, len(rows), scale="moderate").band
            evidence = tuple(
                catalog[i].text
                for r in rows
                if r["source_ids"]
                for i in r["source_ids"][:1]
            )
            scores.append(
                CriterionScore(
                    "A-05",
                    a05.title,
                    score,
                    f"Objective gauging: {matched}/{len(rows)} objectives supported "
                    f"({pct:.1f}%); deterministic score {score}.",
                    evidence=evidence,
                )
            )
    scores_by_id = {s.criterion_id: s for s in scores}
    expected = [c.criterion_code for c in criteria]
    if set(scores_by_id) != set(expected):
        raise AgentExecutionError("Current Coordinator official criterion set mismatch")
    ordered = tuple(scores_by_id[c] for c in expected)
    crows = facts["curriculum"]["rows"]
    c_matches = tuple(
        CurriculumObjectiveMatch(
            objective_id=r["objective_id"],
            objective_text=next(
                o.text
                for o in inventory.objectives
                if o.objective_id == r["objective_id"]
            ),
            matched=bool(r["source_ids"]),
            excerpt=catalog[r["source_ids"][0]].text if r["source_ids"] else "",
            rejected=False,
        )
        for r in crows
    )
    cscore = ratio_band(
        sum(x.matched for x in c_matches), len(c_matches), scale="moderate"
    ).band
    advisory = CoordinatorAlignmentAdvisory(
        contract="coordinator_alignment.v1",
        criterion_id="C-01",
        criterion_title="Curriculum Alignment",
        advisory_only=True,
        score=cscore,
        justification=(
            f"Curriculum alignment: {sum(x.matched for x in c_matches)}/"
            f"{len(c_matches)} objectives supported; deterministic score {cscore}."
        ),
        objective_matches=c_matches,
    )
    facts["curriculum"]["score"] = cscore
    metadata = {
        "execution_contract": CONTRACT,
        "current_bundle": facts,
        "group_prompts": {
            g.unit_key: (
                f"Source inventory prompt: see captured generation {g.unit_key}."
                if g.unit_key.startswith("inventory-")
                else g.prompt_text
            )
            for g in generations
        },
        "group_responses": {
            **{g.unit_key: g.response_json for g in generations},
            "__current_bundle__": facts,
        },
        "envelope_status": {
            **{
                generation.unit_key: generation.envelope_status
                for generation in generations
            },
            "__current_bundle__": "ok",
        },
    }
    prov = {
        "requested_model": adapter.requested_model,
        "actual_model": adapter.actual_model
        if adapter.actual_model != "unknown"
        else adapter.requested_model,
        "repair_occurred": repaired_any,
        "grouped_calls": len(generations),
        "logical_calls": adapter.telemetry.get("call_count", 0),
        "physical_attempts": adapter.telemetry.get("attempt_count", 0),
    }
    return AgentEvaluationResult(
        "coordinator",
        evaluation_id,
        document_id,
        sum(s.score for s in ordered) / len(ordered),
        ordered,
        "Coordinator criteria scored deterministically.",
        adapter.actual_model
        if adapter.actual_model != "unknown"
        else adapter.requested_model,
        time.perf_counter() - started,
        len(canonical_source_text.split()),
        prompt_version_id=prompt_version_id,
        metadata=metadata,
        provenance=prov,
        advisory_outputs=advisory,
        generations=tuple(generations),
    )


__all__ = ["CONTRACT", "run_current"]
