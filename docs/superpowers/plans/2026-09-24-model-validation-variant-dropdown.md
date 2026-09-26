# Model Validation Variant Dropdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Compare tab with a **Model** dropdown (Base model / Fine-tuned adapter) and a **Target** dropdown on **+ New Benchmark Run**, so one submit creates one run.

**Architecture:** `create_model_validation` already persists `model_variant` and `lora_scale`; the paired-run wrapper `create_adapter_comparison` is deleted and the variant moves onto `ModelValidationCreateRequest`, with the LoRA scale derived from it inside the service. The frontend merges the single-agent behavior of the Compare form into `useModelValidationFormState` / `ValidationPreparationForm` and deletes the Compare form, hook, API call, types and tab.

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic, pytest (`cd apps && uv run --project server pytest`); React 18 + TanStack Query, vitest + Testing Library (`cd apps/admin && npx vitest run`).

**Spec:** `docs/superpowers/specs/2026-09-24-model-validation-variant-dropdown-design.md`

## Global Constraints

- **Stack on earlier work (user request):** implementation branch `feat/model-validation-variant-dropdown` is built on `feat/training-data-readiness` with the SME/ITSO manifest-gate commit `1c868cd` (branch `fix/sme-itso-manifest-gate`) cherry-picked underneath. Task 0 sets this up.
- No database migration. `model_validations.model_variant`, `model_validations.compare_group_id` and `evaluation_jobs.lora_scale` all stay; new rows write `compare_group_id = NULL`.
- `model_variant: None` must behave exactly as today: no adapter check, no `lora_scale`, no `lora` field in the request.
- Scale mapping, decided before any DB row exists: `adapter` → `1.0` (refuse with `InvalidEvaluationTargetError` if no adapter is loaded); `base` → `0.0` if an adapter is loaded, otherwise no scale (`None`) but the row is still labelled `base`.
- Adapter requires a single-agent target (`target_agent != "all"`); rejected at the schema level.
- Coordinator is not offered in the Target picker (it needs a curriculum picker).
- The Compare tab, `AdapterComparisonForm`, its hook, `compareAdapter`, the `AdapterComparison*` types/schemas, and `POST /model-validations/compare` are deleted.
- Analytics stay mixed across variants; no side-by-side view (both are explicit follow-ups, not part of this plan).
- Backend style: ruff, line length 88, absolute `server.*` imports; run everything via `cd apps && uv run --project server ...`.
- Frontend style: single quotes, 100-column lines, trailing commas. **Never run prettier across a directory** (no committed config; on this Windows checkout it rewrites quotes and line endings). Format only by hand.
- Repo rule: no `Co-Authored-By` trailers in commits. The user commits manually: at every **Commit** step, stop and confirm with the user before running `git commit` unless they have already authorized committing for this session.

## Review Focus

1. **Endpoint drops between the readiness probe and the adapter check** → 503 with "Could not reach the LLM endpoint to check for a loaded adapter." (Task 1, API test).
2. **Switching to Adapter while "All agents" is selected, then submitting** → the target becomes unselected and submit stays disabled; the API also rejects adapter + all (Task 1 schema test, Task 2 hook test).
3. **Two runs of different variants created back to back** never share a scale (Task 1 service test).
4. **Catalog missing the chosen agent** (for example after a catalog reload) → no criteria in scope, submit disabled rather than an empty request (Task 2 hook test).
5. **Stale sub-tab:** the form's active agent tab defaults to `'sme'`; with Target = GAD no tab may end up active-less (Task 3 form test).
6. **Old rows** with `model_variant = null` and a stray `compare_group_id` still render; no code path may require `compare_group_id` (covered by existing `ValidationDetail`/`helpers` tests, re-run in Task 5).

---

### Task 0: Stack the implementation branch

**Files:** none (git only). The spec and this plan are currently untracked files in the working tree; they carry over the checkout.

- [ ] **Step 1: Confirm a clean starting point**

Run: `git status --short`
Expected: only `?? docs/superpowers/specs/2026-09-24-model-validation-variant-dropdown-design.md` and `?? docs/superpowers/plans/2026-09-24-model-validation-variant-dropdown.md`.

- [ ] **Step 2: Create the branch on top of the readiness work**

Run: `git checkout -b feat/model-validation-variant-dropdown feat/training-data-readiness`
Expected: `Switched to a new branch 'feat/model-validation-variant-dropdown'`

- [ ] **Step 3: Bring in the manifest-gate fix underneath the new work**

Run: `git cherry-pick 1c868cd`
Expected: one new commit `fix(agents): replace hardcoded adapter gate in SME and ITSO with manifest-driven validation`, no conflicts (that commit touches only `agents/sme`, `agents/itso` and their tests; the readiness branch touches `training_data` and `admin` UI).

- [ ] **Step 4: Verify the stack**

Run: `git log --oneline -6`
Expected (newest first): the cherry-picked gate fix, then `chore: add adapter evaluation report...`, `feat(admin): show dataset readiness...`, `feat(training-data): add dataset readiness preview...`, then `Merge pull request #343`.

- [ ] **Step 5: Baseline both suites before changing anything**

Run: `cd apps && uv run --project server pytest server/tests/admin/test_model_validation.py server/tests/admin/test_model_validation_api.py -q`
Expected: all pass.

Run: `cd apps/admin && npx vitest run src/features/model-validation`
Expected: all pass.

- [ ] **Step 6: Commit the spec and plan**

```bash
git add docs/superpowers/specs/2026-09-24-model-validation-variant-dropdown-design.md docs/superpowers/plans/2026-09-24-model-validation-variant-dropdown.md
git commit -m "docs: spec and plan for the Model Validation variant dropdown"
```

---

### Task 1: Backend — variant on the standard request, compare wrapper removed

**Files:**
- Modify: `apps/server/modules/admin/schemas.py` (`ModelValidationCreateRequest` ~lines 182-211; delete `AdapterComparisonCreateRequest`/`AdapterComparisonResponse` ~lines 214-230 and their `__all__` entries ~lines 356-357)
- Modify: `apps/server/modules/admin/model_validation_service.py` (imports lines 37-39, `__all__` line 66, `create_model_validation` signature/body lines 178-361, delete `create_adapter_comparison` lines 385-432)
- Modify: `apps/server/modules/admin/router.py` (imports lines 15, 30-31; standard route `submit_model_validation` ~lines 448-488; delete `submit_adapter_comparison` ~lines 491-535)
- Test: `apps/server/tests/admin/test_model_validation.py`, `apps/server/tests/admin/test_model_validation_api.py`

**Interfaces:**
- Produces: `ModelValidationCreateRequest.model_variant: Literal["base", "adapter"] | None = None`.
- Produces: `_resolve_lora_scale(model_variant: str | None) -> float | None` (module-private in `model_validation_service.py`).
- Produces: `create_model_validation(request, *, created_by, created_by_role=None, db)` — the `model_variant`, `compare_group_id`, `lora_scale` keyword arguments are removed.
- Consumes: `check_lora_adapter_loaded() -> bool` from `server.core.llm` (may raise `InfrastructureUnavailableError`).

- [ ] **Step 1: Write the failing service tests**

Add to `apps/server/tests/admin/test_model_validation.py`, directly after `test_create_model_validation_targets_one_agent`:

```python
def _sme_variant_request(slm, expected_scores, **extra):
    from server.modules.admin.schemas import ModelValidationCreateRequest

    sme_only = [item for item in expected_scores if item["agent_id"] == "sme"]
    return ModelValidationCreateRequest.model_validate(
        {
            "document_id": slm.document_id,
            "target_agent": "sme",
            "expected_scores": sme_only,
            **extra,
        }
    )


def _set_adapter_loaded(monkeypatch, value) -> None:
    monkeypatch.setattr(
        "server.modules.admin.model_validation_service.check_lora_adapter_loaded",
        (lambda: value) if not callable(value) else value,
    )


def test_model_variant_none_sends_no_scale_and_skips_the_adapter_check(
    admin_user, db_session, monkeypatch
) -> None:
    from server.modules.admin.model_validation_service import create_model_validation

    def _must_not_run():
        raise AssertionError("adapter check must not run when model_variant is None")

    _set_adapter_loaded(monkeypatch, _must_not_run)
    expected_scores, slm = _setup_validation(db_session, admin_user)
    req = _sme_variant_request(slm, expected_scores)
    assert req.model_variant is None

    response = create_model_validation(
        req, created_by=admin_user.user_id, created_by_role="admin", db=db_session
    )

    validation = db_session.get(ModelValidation, response.validation_id)
    job = db_session.get(EvaluationJob, response.evaluation_id)
    assert validation.model_variant is None
    assert validation.compare_group_id is None
    assert job.lora_scale is None


def test_adapter_variant_rejects_all_agents(admin_user, db_session) -> None:
    from pydantic import ValidationError
    from server.modules.admin.schemas import ModelValidationCreateRequest

    expected_scores, slm = _setup_validation(db_session, admin_user)

    with pytest.raises(ValidationError, match="requires a single target_agent"):
        ModelValidationCreateRequest.model_validate(
            {
                "document_id": slm.document_id,
                "partial_without_curriculum": True,
                "model_variant": "adapter",
                "expected_scores": expected_scores,
            }
        )


def test_adapter_variant_refuses_when_no_adapter_is_loaded(
    admin_user, db_session, monkeypatch
) -> None:
    from server.modules.admin.model_validation_service import create_model_validation
    from server.modules.evaluations.exceptions import InvalidEvaluationTargetError

    _set_adapter_loaded(monkeypatch, False)
    expected_scores, slm = _setup_validation(db_session, admin_user)
    req = _sme_variant_request(slm, expected_scores, model_variant="adapter")

    with pytest.raises(InvalidEvaluationTargetError, match="no adapter is loaded"):
        create_model_validation(
            req, created_by=admin_user.user_id, created_by_role="admin", db=db_session
        )

    assert db_session.query(EvaluationJob).count() == 0
    assert db_session.query(ModelValidation).count() == 0


def test_adapter_variant_applies_scale_one_when_an_adapter_is_loaded(
    admin_user, db_session, monkeypatch
) -> None:
    from server.modules.admin.model_validation_service import create_model_validation

    _set_adapter_loaded(monkeypatch, True)
    expected_scores, slm = _setup_validation(db_session, admin_user)
    req = _sme_variant_request(slm, expected_scores, model_variant="adapter")

    response = create_model_validation(
        req, created_by=admin_user.user_id, created_by_role="admin", db=db_session
    )

    validation = db_session.get(ModelValidation, response.validation_id)
    job = db_session.get(EvaluationJob, response.evaluation_id)
    assert validation.model_variant == "adapter"
    assert validation.compare_group_id is None
    assert job.lora_scale == 1.0
    assert job.target_agent == "sme"


def test_base_variant_forces_the_adapter_off_when_one_is_loaded(
    admin_user, db_session, monkeypatch
) -> None:
    from server.modules.admin.model_validation_service import create_model_validation

    _set_adapter_loaded(monkeypatch, True)
    expected_scores, slm = _setup_validation(db_session, admin_user)
    req = _sme_variant_request(slm, expected_scores, model_variant="base")

    response = create_model_validation(
        req, created_by=admin_user.user_id, created_by_role="admin", db=db_session
    )

    validation = db_session.get(ModelValidation, response.validation_id)
    job = db_session.get(EvaluationJob, response.evaluation_id)
    assert validation.model_variant == "base"
    assert job.lora_scale == 0.0


def test_base_variant_sends_no_scale_when_no_adapter_is_loaded(
    admin_user, db_session, monkeypatch
) -> None:
    from server.modules.admin.model_validation_service import create_model_validation

    _set_adapter_loaded(monkeypatch, False)
    expected_scores, slm = _setup_validation(db_session, admin_user)
    req = _sme_variant_request(slm, expected_scores, model_variant="base")

    response = create_model_validation(
        req, created_by=admin_user.user_id, created_by_role="admin", db=db_session
    )

    validation = db_session.get(ModelValidation, response.validation_id)
    job = db_session.get(EvaluationJob, response.evaluation_id)
    assert validation.model_variant == "base"
    assert job.lora_scale is None


def test_runs_of_different_variants_keep_separate_scales(
    admin_user, db_session, monkeypatch
) -> None:
    from server.modules.admin.model_validation_service import create_model_validation

    _set_adapter_loaded(monkeypatch, True)
    expected_scores, slm = _setup_validation(db_session, admin_user)

    adapter_response = create_model_validation(
        _sme_variant_request(slm, expected_scores, model_variant="adapter"),
        created_by=admin_user.user_id,
        created_by_role="admin",
        db=db_session,
    )
    base_response = create_model_validation(
        _sme_variant_request(slm, expected_scores, model_variant="base"),
        created_by=admin_user.user_id,
        created_by_role="admin",
        db=db_session,
    )

    adapter_job = db_session.get(EvaluationJob, adapter_response.evaluation_id)
    base_job = db_session.get(EvaluationJob, base_response.evaluation_id)
    assert adapter_job.lora_scale == 1.0
    assert base_job.lora_scale == 0.0
```

Then **delete** these five functions from the same file (they exercise the removed wrapper and removed keyword arguments): `test_create_adapter_comparison_refuses_when_no_adapter_loaded`, `test_create_adapter_comparison_creates_a_linked_pair`, `test_create_model_validation_sets_compare_fields_when_provided`, `test_create_adapter_comparison_supports_coordinator_with_curriculum_id`, `test_create_adapter_comparison_rejects_all_agents`.

- [ ] **Step 2: Write the failing API tests**

In `apps/server/tests/admin/test_model_validation_api.py`, **delete** `test_compare_endpoint_creates_a_linked_pair` and `test_compare_endpoint_returns_503_when_llm_endpoint_unreachable`, and add in their place:

```python
def _sme_only_body(slm, expected_scores, **extra):
    sme_only = [item for item in expected_scores if item["agent_id"] == "sme"]
    return {
        "document_id": str(slm.document_id),
        "target_agent": "sme",
        "expected_scores": sme_only,
        **extra,
    }


def test_standard_route_accepts_the_adapter_variant(
    client: TestClient, auth_cookies_admin, admin_user, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(
        "server.modules.admin.model_validation_service.check_lora_adapter_loaded",
        lambda: True,
    )
    expected_scores, slm = _setup_validation(db_session, admin_user)
    _auth(client, auth_cookies_admin)

    resp = client.post(
        "/api/v1/admin/model-validations",
        json=_sme_only_body(slm, expected_scores, model_variant="adapter"),
    )

    assert resp.status_code == 202
    body = resp.json()
    assert body["model_variant"] == "adapter"
    assert body["compare_group_id"] is None


def test_standard_route_returns_422_when_the_adapter_is_not_loaded(
    client: TestClient, auth_cookies_admin, admin_user, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(
        "server.modules.admin.model_validation_service.check_lora_adapter_loaded",
        lambda: False,
    )
    expected_scores, slm = _setup_validation(db_session, admin_user)
    _auth(client, auth_cookies_admin)

    resp = client.post(
        "/api/v1/admin/model-validations",
        json=_sme_only_body(slm, expected_scores, model_variant="adapter"),
    )

    assert resp.status_code == 422
    assert "no adapter is loaded" in resp.json()["detail"]


def test_standard_route_rejects_the_adapter_variant_with_all_agents(
    client: TestClient, auth_cookies_admin, admin_user, db_session
) -> None:
    expected_scores, slm = _setup_validation(db_session, admin_user)
    _auth(client, auth_cookies_admin)

    resp = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "model_variant": "adapter",
            "expected_scores": expected_scores,
        },
    )

    assert resp.status_code == 422


def test_standard_route_returns_503_when_the_adapter_check_cannot_reach_the_endpoint(
    client: TestClient, auth_cookies_admin, admin_user, db_session, monkeypatch
) -> None:
    from server.core.exceptions import InfrastructureUnavailableError

    def _raise():
        raise InfrastructureUnavailableError("endpoint down")

    monkeypatch.setattr(
        "server.modules.admin.model_validation_service.check_lora_adapter_loaded",
        _raise,
    )
    expected_scores, slm = _setup_validation(db_session, admin_user)
    _auth(client, auth_cookies_admin)

    resp = client.post(
        "/api/v1/admin/model-validations",
        json=_sme_only_body(slm, expected_scores, model_variant="base"),
    )

    assert resp.status_code == 503
    assert "loaded adapter" in resp.json()["detail"]


def test_the_compare_route_no_longer_exists(
    client: TestClient, auth_cookies_admin, admin_user, db_session
) -> None:
    expected_scores, slm = _setup_validation(db_session, admin_user)
    _auth(client, auth_cookies_admin)

    resp = client.post(
        "/api/v1/admin/model-validations/compare",
        json=_sme_only_body(slm, expected_scores),
    )

    assert resp.status_code in (404, 405)
```

- [ ] **Step 3: Run the new tests to verify they fail**

Run: `cd apps && uv run --project server pytest server/tests/admin/test_model_validation.py server/tests/admin/test_model_validation_api.py -k "variant or standard_route or compare_route" -q`
Expected: FAIL (`extra="forbid"` rejects `model_variant`; `test_the_compare_route_no_longer_exists` fails with 202).

- [ ] **Step 4: Add the request field and validator**

In `apps/server/modules/admin/schemas.py`, inside `ModelValidationCreateRequest`, add the field directly after `target_agent`:

```python
    target_agent: Literal["all", "sme", "coordinator", "gad", "itso"] = "all"
    model_variant: Literal["base", "adapter"] | None = None
    expected_scores: list[ModelValidationExpectedScoreInput] = Field(min_length=1)
```

and add a second validator after `_validate_single_agent_not_partial`:

```python
    @model_validator(mode="after")
    def _validate_adapter_targets_single_agent(self) -> ModelValidationCreateRequest:
        if self.model_variant == "adapter" and self.target_agent == "all":
            raise ValueError(
                'model_variant="adapter" requires a single target_agent, not "all".'
            )
        return self
```

Also update the class docstring's last sentence to mention it: append `model_variant selects the plain model ("base") or the fine-tuned adapter ("adapter"); None leaves the LoRA scale untouched.`

Delete `AdapterComparisonCreateRequest` and `AdapterComparisonResponse` and remove `"AdapterComparisonCreateRequest"` and `"AdapterComparisonResponse"` from `__all__`.

- [ ] **Step 5: Derive the scale in the service and drop the wrapper**

In `apps/server/modules/admin/model_validation_service.py`:

1. Remove `AdapterComparisonCreateRequest,` and `AdapterComparisonResponse,` from the `.schemas` import, and remove `"create_adapter_comparison",` from `__all__`.

2. Add this helper directly above `create_model_validation`:

```python
def _resolve_lora_scale(model_variant: str | None) -> float | None:
    """Map a run's model variant to the LoRA scale sent to the model server.

    Runs before any row exists, so a refusal never leaves an orphan job.
    ``None`` is the historical behavior: no adapter check, no scale.
    """
    if model_variant is None:
        return None
    adapter_loaded = check_lora_adapter_loaded()
    if model_variant == "adapter":
        if not adapter_loaded:
            raise InvalidEvaluationTargetError(
                "no adapter is loaded on the server; ask the host owner to load "
                "one first (see training/serving-lora-adapter.md)"
            )
        return 1.0
    # Base: force an applied adapter off. With none loaded there is nothing to
    # turn off, and sending a lora field to such a server is unverified.
    return 0.0 if adapter_loaded else None
```

3. Change the `create_model_validation` signature and first lines. Replace:

```python
    db: Any,
    model_variant: str | None = None,
    compare_group_id: uuid.UUID | None = None,
    lora_scale: float | None = None,
) -> ModelValidationResponse:
    """Create an evaluation job with private criterion-level benchmarks.

    All persistence (evaluation job, form snapshots, validation record,
    expected criterion rows) is committed atomically so a failure after any
    step never leaves an orphan job.
    """
    is_partial = bool(request.partial_without_curriculum)
```

with:

```python
    db: Any,
) -> ModelValidationResponse:
    """Create an evaluation job with private criterion-level benchmarks.

    All persistence (evaluation job, form snapshots, validation record,
    expected criterion rows) is committed atomically so a failure after any
    step never leaves an orphan job. ``request.model_variant`` decides the
    LoRA scale for the run (see ``_resolve_lora_scale``).
    """
    lora_scale = _resolve_lora_scale(request.model_variant)
    is_partial = bool(request.partial_without_curriculum)
```

4. Replace the `ModelValidation(...)` construction:

```python
        validation = ModelValidation(
            validation_id=validation_id,
            evaluation_id=evaluation.evaluation_id,
            created_by=created_by,
            model_variant=request.model_variant,
        )
```

(`compare_group_id` is no longer set, so it stays `NULL`.) Leave the `if lora_scale is not None:` block above it untouched.

5. Delete the whole `create_adapter_comparison` function.

- [ ] **Step 6: Update the router**

In `apps/server/modules/admin/router.py`:

1. Remove `create_adapter_comparison,` from the service import and `AdapterComparisonCreateRequest,` / `AdapterComparisonResponse,` from the schemas import.
2. Delete the whole `submit_adapter_comparison` route (the `@router.post("/model-validations/compare", ...)` decorator through its final `return response`).
3. In `submit_model_validation`, add the 503 mapping after the `InvalidEvaluationTargetError` handler:

```python
    except InvalidEvaluationTargetError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except InfrastructureUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not reach the LLM endpoint to check for a loaded adapter.",
        ) from exc
    background_tasks.add_task(drain_evaluation_queue)
    return response
```

(`InfrastructureUnavailableError` is already imported at the top of the file.)

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd apps && uv run --project server ruff check --fix server/modules/admin server/tests/admin && uv run --project server ruff format server/modules/admin/schemas.py server/modules/admin/model_validation_service.py server/modules/admin/router.py server/tests/admin/test_model_validation.py server/tests/admin/test_model_validation_api.py`
Expected: no remaining errors.

Run: `cd apps && uv run --project server pytest server/tests/admin server/tests/core/test_llm.py server/tests/migrations/test_adapter_compare_columns_migration.py -q`
Expected: all pass (the migration test still passes because the columns stay).

- [ ] **Step 8: Commit**

```bash
git add apps/server/modules/admin/schemas.py apps/server/modules/admin/model_validation_service.py apps/server/modules/admin/router.py apps/server/tests/admin/test_model_validation.py apps/server/tests/admin/test_model_validation_api.py
git commit -m "feat(admin): choose base or adapter per benchmark run; remove paired compare runs"
```

---

### Task 2: Frontend — types, API client and form state

**Files:**
- Modify: `apps/admin/src/features/model-validation/types.ts` (`ModelValidationCreateBody`; delete `AdapterComparisonCreateBody`, `AdapterComparisonResponse`)
- Modify: `apps/admin/src/features/model-validation/api/modelValidation.api.ts` (delete `compareAdapter` and its type imports)
- Modify: `apps/admin/src/features/model-validation/api/__tests__/modelValidation.api.test.ts` (delete the compare test)
- Modify: `apps/admin/src/features/model-validation/hooks/useModelValidationFormState.ts`
- Test: `apps/admin/src/features/model-validation/hooks/__tests__/useModelValidationFormState.test.tsx`

**Interfaces:**
- Produces: `type ModelVariant = 'base' | 'adapter'` and `type TargetAgent = 'all' | 'sme' | 'gad' | 'itso'`, both exported from `useModelValidationFormState.ts`.
- Produces on the hook's return value: `modelVariant: ModelVariant`, `setModelVariant(next: ModelVariant): void`, `targetAgent: TargetAgent | null`, `setTargetAgent(next: TargetAgent | null): void`. `criterionDefinitions` now means the definitions **scoped to the target** (all three partial agents, one agent, or `[]` when the target is unselected).
- Produces: `ModelValidationCreateBody` gains `model_variant?: 'base' | 'adapter'` and `target_agent?: 'sme' | 'gad' | 'itso'`.

- [ ] **Step 1: Write the failing hook tests**

Append inside the `describe('useModelValidationFormState', ...)` block of `hooks/__tests__/useModelValidationFormState.test.tsx` (before its closing `});`):

```tsx
  function mockUploadedReadyDocument() {
    vi.spyOn(documentsApi, 'uploadDocument').mockResolvedValue({
      documentId: 'doc-ready-1',
      title: 'SLM 1',
      sourceType: 'slm',
      processingStatus: 'PROCESSED',
      academicYear: null,
      courseCode: null,
      courseTitle: null,
      lessonTitle: null,
    });
    vi.spyOn(documentsApi, 'getDocument').mockResolvedValue(mockReadyDoc);
  }

  function captureSubmittedBody() {
    const captured: { body?: ModelValidationCreateBody } = {};
    vi.spyOn(modelValidationApi, 'createModelValidation').mockImplementation(async (body) => {
      captured.body = body;
      const created: ModelValidationItem = {
        validation_id: 'val-1',
        evaluation_id: 'eval-1',
        document_id: body.document_id,
        document_title: 'SLM 1',
        model_variant: body.model_variant ?? null,
        compare_group_id: null,
        partial_without_curriculum: body.partial_without_curriculum,
        bound_forms: [],
        criterion_scores: [],
        absolute_error: null,
        latency_seconds: null,
        score_perplexity: null,
        toxicity_score: null,
        toxicity_label: null,
        toxicity_explanation: null,
        toxicity_model: null,
        toxicity_error: null,
        status: 'SUBMITTED',
        error_message: null,
        created_at: '2026-09-24T00:00:00Z',
      };
      return created;
    });
    return captured;
  }

  async function uploadDocument(result: { current: ReturnType<typeof useModelValidationFormState> }) {
    await act(async () => {
      result.current.uploadMutation.mutate({
        file: new File(['dummy'], 'slm.pdf', { type: 'application/pdf' }),
        title: 'SLM 1',
        program: 'BSCS',
      });
    });
    await waitFor(() => {
      expect(result.current.uploadedDocumentReady).toBe(true);
    });
  }

  it('defaults to the Base model targeting all agents, unchanged from the old flow', async () => {
    vi.spyOn(modelValidationApi, 'getModelValidationCriteria').mockResolvedValue(
      mockCriteriaCatalog,
    );

    const { result } = renderHook(() => useModelValidationFormState(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.criterionDefinitions.length).toBe(3);
    });
    expect(result.current.modelVariant).toBe('base');
    expect(result.current.targetAgent).toBe('all');
  });

  it('un-selects the target when switching to Adapter while All agents is selected', async () => {
    vi.spyOn(modelValidationApi, 'getModelValidationCriteria').mockResolvedValue(
      mockCriteriaCatalog,
    );

    const { result } = renderHook(() => useModelValidationFormState(), {
      wrapper: createWrapper(),
    });
    await waitFor(() => {
      expect(result.current.criterionDefinitions.length).toBe(3);
    });

    act(() => {
      result.current.setModelVariant('adapter');
    });

    expect(result.current.modelVariant).toBe('adapter');
    expect(result.current.targetAgent).toBeNull();
    expect(result.current.criterionDefinitions).toEqual([]);
    expect(result.current.allCriterionScoresComplete).toBe(false);
    expect(result.current.canSubmitEvaluation).toBe(false);
  });

  it('scopes criteria to one agent and keeps it when switching back to Base', async () => {
    vi.spyOn(modelValidationApi, 'getModelValidationCriteria').mockResolvedValue(
      mockCriteriaCatalog,
    );

    const { result } = renderHook(() => useModelValidationFormState(), {
      wrapper: createWrapper(),
    });
    await waitFor(() => {
      expect(result.current.criterionDefinitions.length).toBe(3);
    });

    act(() => {
      result.current.setModelVariant('adapter');
      result.current.setTargetAgent('sme');
    });
    expect(result.current.criterionDefinitions.map((a) => a.agent_id)).toEqual(['sme']);

    act(() => {
      result.current.setModelVariant('base');
    });
    expect(result.current.targetAgent).toBe('sme');
    expect(result.current.criterionDefinitions.map((a) => a.agent_id)).toEqual(['sme']);
  });

  it('submits a single-agent adapter run without the partial flag or acknowledgement', async () => {
    vi.spyOn(modelValidationApi, 'getModelValidationCriteria').mockResolvedValue(
      mockCriteriaCatalog,
    );
    mockUploadedReadyDocument();
    const captured = captureSubmittedBody();

    const { result } = renderHook(() => useModelValidationFormState(), {
      wrapper: createWrapper(),
    });
    await waitFor(() => {
      expect(result.current.criterionDefinitions.length).toBe(3);
    });
    await uploadDocument(result);

    act(() => {
      result.current.setModelVariant('adapter');
      result.current.setTargetAgent('sme');
      result.current.setExpectedScores({ 'sme:crit-sme-1': '4' });
    });

    expect(result.current.partialChoiceAcknowledged).toBe(false);
    expect(result.current.canSubmitEvaluation).toBe(true);

    await act(async () => {
      result.current.handleStart();
    });

    expect(captured.body?.model_variant).toBe('adapter');
    expect(captured.body?.target_agent).toBe('sme');
    expect(captured.body?.partial_without_curriculum).toBe(false);
    expect(captured.body?.expected_scores).toEqual([
      {
        agent_id: 'sme',
        rubric_set_id: 'set-sme-123',
        rubric_criterion_id: 'crit-sme-1',
        expected_score: 4,
      },
    ]);
  });

  it('still needs the partial acknowledgement for a Base run over all agents', async () => {
    vi.spyOn(modelValidationApi, 'getModelValidationCriteria').mockResolvedValue(
      mockCriteriaCatalog,
    );
    mockUploadedReadyDocument();
    const captured = captureSubmittedBody();

    const { result } = renderHook(() => useModelValidationFormState(), {
      wrapper: createWrapper(),
    });
    await waitFor(() => {
      expect(result.current.criterionDefinitions.length).toBe(3);
    });
    await uploadDocument(result);

    act(() => {
      result.current.setExpectedScores({
        'sme:crit-sme-1': '4',
        'gad:crit-gad-1': '3',
        'itso:crit-itso-1': '4',
      });
    });
    expect(result.current.canSubmitEvaluation).toBe(false);

    act(() => {
      result.current.setPartialChoiceAcknowledged(true);
    });
    expect(result.current.canSubmitEvaluation).toBe(true);

    await act(async () => {
      result.current.handleStart();
    });

    expect(captured.body?.model_variant).toBe('base');
    expect(captured.body?.partial_without_curriculum).toBe(true);
    expect(captured.body?.target_agent).toBeUndefined();
  });

  it('blocks submission when the chosen agent is missing from the catalog', async () => {
    vi.spyOn(modelValidationApi, 'getModelValidationCriteria').mockResolvedValue({
      agents: mockCriteriaCatalog.agents.filter((agent) => agent.agent_id !== 'gad'),
      total_criteria: 3,
    });

    const { result } = renderHook(() => useModelValidationFormState(), {
      wrapper: createWrapper(),
    });
    await waitFor(() => {
      expect(result.current.criterionDefinitions.length).toBe(2);
    });

    act(() => {
      result.current.setTargetAgent('gad');
    });

    expect(result.current.criterionDefinitions).toEqual([]);
    expect(result.current.allCriterionScoresComplete).toBe(false);
    expect(result.current.canSubmitEvaluation).toBe(false);
  });
```

Also, in the existing test `'submits every expected score as exact ...'`, add after `expect(submittedBody?.partial_without_curriculum).toBe(true);`:

```tsx
    expect(submittedBody?.model_variant).toBe('base');
```

- [ ] **Step 2: Run the hook tests to verify they fail**

Run: `cd apps/admin && npx vitest run src/features/model-validation/hooks/__tests__/useModelValidationFormState.test.tsx`
Expected: FAIL (`modelVariant`/`setModelVariant`/`targetAgent` are undefined).

- [ ] **Step 3: Update the types**

In `types.ts`, replace `ModelValidationCreateBody` and delete the two `AdapterComparison*` interfaces:

```ts
export interface ModelValidationCreateBody {
  document_id: string;
  syllabus_id?: string | null;
  curriculum_id?: string | null;
  partial_without_curriculum: boolean;
  target_agent?: 'sme' | 'gad' | 'itso';
  model_variant?: 'base' | 'adapter';
  expected_scores: ExpectedCriterionScoreInput[];
}
```

- [ ] **Step 4: Update the API client and its test**

In `api/modelValidation.api.ts`: remove `AdapterComparisonCreateBody,` and `AdapterComparisonResponse,` from the type import and delete the whole `compareAdapter` entry.

In `api/__tests__/modelValidation.api.test.ts`: delete the `it('calls the compare endpoint with the exact body', ...)` block and remove `AdapterComparisonCreateBody` from that file's type import if it becomes unused.

- [ ] **Step 5: Implement the form state**

In `hooks/useModelValidationFormState.ts`:

1. Add the exported types after the imports:

```ts
export type ModelVariant = 'base' | 'adapter';
export type TargetAgent = 'all' | 'sme' | 'gad' | 'itso';
```

2. Add state next to the existing `useState` calls:

```ts
  const [modelVariant, setModelVariantState] = useState<ModelVariant>('base');
  const [targetAgent, setTargetAgent] = useState<TargetAgent | null>('all');
```

3. Add the variant setter (after the state block):

```ts
  // An adapter is trained for one agent, so "all agents" is not a valid adapter
  // target: switching to Adapter drops it and the admin must pick an agent.
  const setModelVariant = (next: ModelVariant) => {
    setModelVariantState(next);
    if (next === 'adapter' && targetAgent === 'all') setTargetAgent(null);
  };
```

4. Replace the `criterionDefinitions` derivation:

```ts
  const rawAgents = criterionCatalog.data?.agents ?? [];
  const partialAgentDefinitions = rawAgents.filter((agent) =>
    isPartialValidationAgent(agent.agent_id),
  );
  const criterionDefinitions =
    targetAgent === 'all'
      ? partialAgentDefinitions
      : targetAgent
        ? partialAgentDefinitions.filter((agent) => agent.agent_id === targetAgent)
        : [];
```

(everything that already used `criterionDefinitions` — `orderedCriterionKeys`, `allCriterionScoresComplete`, `handleStart` — now follows the target automatically.)

5. Replace `canSubmitEvaluation`:

```ts
  const canSubmitEvaluation =
    uploadedDocumentReady &&
    allCriterionScoresComplete &&
    (targetAgent !== 'all' || partialChoiceAcknowledged);
```

6. Replace the body built in `handleStart`:

```ts
  const handleStart = () => {
    if (!uploaded || !canSubmitEvaluation) return;
    validationMutation.mutate({
      document_id: uploaded.documentId,
      model_variant: modelVariant,
      ...(targetAgent === 'all'
        ? { partial_without_curriculum: true }
        : { partial_without_curriculum: false, target_agent: targetAgent! }),
      expected_scores: criterionDefinitions.flatMap((agent) => {
        const crits =
          agent.domains && agent.domains.length > 0
            ? agent.domains.flatMap((d) => d.criteria)
            : agent.criteria;
        return crits.map((criterion) => ({
          agent_id: agent.agent_id as 'sme' | 'gad' | 'itso',
          rubric_set_id: agent.rubric_set_id,
          rubric_criterion_id: criterion.rubric_criterion_id,
          expected_score: Number(
            expectedScores[
              criterionKey(agent.agent_id, criterion.rubric_criterion_id || criterion.criterion_id!)
            ],
          ),
        }));
      }),
    });
  };
```

7. Add to the returned object: `modelVariant, setModelVariant, targetAgent, setTargetAgent,`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd apps/admin && npx vitest run src/features/model-validation/hooks/__tests__/useModelValidationFormState.test.tsx src/features/model-validation/api`
Expected: PASS.

Run: `cd apps/admin && npx tsc --noEmit`
Expected: errors only in files Tasks 3-4 change (`ValidationPreparationForm.test.tsx` mock form, `AdapterComparisonForm*`, `useAdapterComparisonFormState*`, `ModelValidationPage.tsx`); none in the files touched here.

- [ ] **Step 7: Commit**

```bash
git add apps/admin/src/features/model-validation/types.ts apps/admin/src/features/model-validation/api apps/admin/src/features/model-validation/hooks/useModelValidationFormState.ts apps/admin/src/features/model-validation/hooks/__tests__/useModelValidationFormState.test.tsx
git commit -m "feat(admin): model variant and target agent in the benchmark form state"
```

---

### Task 3: Frontend — Model and Target controls in the form

**Files:**
- Modify: `apps/admin/src/features/model-validation/components/ValidationPreparationForm.tsx`
- Test: `apps/admin/src/features/model-validation/components/__tests__/ValidationPreparationForm.test.tsx`

**Interfaces:**
- Consumes: `form.modelVariant`, `form.setModelVariant`, `form.targetAgent`, `form.setTargetAgent`, `form.criterionDefinitions` (scoped) from Task 2, plus the exported types `ModelVariant` and `TargetAgent`.

- [ ] **Step 1: Write the failing form tests**

In `ValidationPreparationForm.test.tsx`, add the four new fields to the `defaultForm` object in `createMockForm` (after `partialChoiceAcknowledged`/`setPartialChoiceAcknowledged`):

```tsx
    modelVariant: 'base',
    setModelVariant: vi.fn(),
    targetAgent: 'all',
    setTargetAgent: vi.fn(),
```

Then add these tests inside `describe('ValidationPreparationForm', ...)` before its closing `});`:

```tsx
  it('renders Model and Target selects defaulting to Base model and All agents', () => {
    render(<ValidationPreparationForm form={createMockForm()} />);

    expect((screen.getByLabelText('Model') as HTMLSelectElement).value).toBe('base');
    expect((screen.getByLabelText('Target') as HTMLSelectElement).value).toBe('all');
  });

  it('disables All agents while the adapter is selected and reports changes', () => {
    const setModelVariant = vi.fn();
    const setTargetAgent = vi.fn();
    const form = createMockForm({
      modelVariant: 'adapter',
      targetAgent: 'sme',
      criterionDefinitions: [mockAgents[0]],
      setModelVariant,
      setTargetAgent,
    });

    render(<ValidationPreparationForm form={form} />);

    const allAgents = screen.getByRole('option', { name: /All agents/ }) as HTMLOptionElement;
    expect(allAgents.disabled).toBe(true);

    fireEvent.change(screen.getByLabelText('Target'), { target: { value: 'gad' } });
    expect(setTargetAgent).toHaveBeenCalledWith('gad');

    fireEvent.change(screen.getByLabelText('Model'), { target: { value: 'base' } });
    expect(setModelVariant).toHaveBeenCalledWith('base');
  });

  it('shows an unselected Target prompt after switching to the adapter from All agents', () => {
    const form = createMockForm({
      modelVariant: 'adapter',
      targetAgent: null,
      criterionDefinitions: [],
      allCriterionScoresComplete: false,
    });

    render(<ValidationPreparationForm form={form} />);

    expect((screen.getByLabelText('Target') as HTMLSelectElement).value).toBe('');
    expect(screen.getByRole('option', { name: /Choose an agent/ })).toBeDefined();
  });

  it('hides the partial-run acknowledgement for a single-agent target', () => {
    const form = createMockForm({
      targetAgent: 'sme',
      criterionDefinitions: [mockAgents[0]],
      uploaded: {
        documentId: 'doc-1',
        title: 'SLM 1',
        sourceType: 'slm',
        processingStatus: 'PROCESSED',
        academicYear: null,
        courseCode: null,
        courseTitle: null,
        lessonTitle: null,
      },
      uploadedDocumentReady: true,
    });

    render(<ValidationPreparationForm form={form} />);

    expect(
      screen.queryByLabelText(/I understand that the Coordinator agent will be skipped/i),
    ).toBeNull();
  });

  it('activates the only in-scope agent tab even though the default tab state is SME', () => {
    const form = createMockForm({
      targetAgent: 'gad',
      criterionDefinitions: [mockAgents[1]],
    });

    render(<ValidationPreparationForm form={form} />);

    const gadTab = screen.getByRole('button', { name: /^GAD/ });
    expect(gadTab.className).toContain('bg-primary');
  });
```

- [ ] **Step 2: Run the form tests to verify they fail**

Run: `cd apps/admin && npx vitest run src/features/model-validation/components/__tests__/ValidationPreparationForm.test.tsx`
Expected: FAIL (no Model/Target controls; partial acknowledgement still shown; GAD tab not active).

- [ ] **Step 3: Add the controls and scope the form**

In `ValidationPreparationForm.tsx`:

1. Add to the destructuring of `form`: `modelVariant, setModelVariant, targetAgent, setTargetAgent,`.

2. Add the type import next to the existing `ModelValidationFormState` import:

```tsx
import type {
  ModelValidationFormState,
  ModelVariant,
  TargetAgent,
} from '../hooks/useModelValidationFormState';
```

3. Directly after `const [activeAgentTab, setActiveAgentTab] = ...` add:

```tsx
  // The default tab state is 'sme'; with a single-agent target that agent may
  // not be in scope, so fall back to the first agent that is.
  const visibleAgentId = criterionDefinitions.some((agent) => agent.agent_id === activeAgentTab)
    ? activeAgentTab
    : criterionDefinitions[0]?.agent_id;
```

4. Replace both occurrences of `(activeAgentTab || criterionDefinitions[0]?.agent_id)` (the `isTabActive` line and the `isVisible` line) with `visibleAgentId`.

5. Insert this card as the first child of the left column, immediately before the `{/* Card 1: Document Metadata & File */}` comment:

```tsx
            {/* Run configuration: which model, and which agent(s) to benchmark */}
            <div className="rounded-md border border-border bg-surface p-5 space-y-4 shadow-none">
              <div className="border-b border-border pb-2.5">
                <h3 className="text-sm font-bold text-text tracking-tight">Run configuration</h3>
              </div>

              <div className="grid gap-3.5 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <label htmlFor="validation-model" className="text-xs font-semibold text-text">
                    Model
                  </label>
                  <select
                    id="validation-model"
                    value={modelVariant}
                    onChange={(event) => setModelVariant(event.target.value as ModelVariant)}
                    className="h-10 w-full rounded-sm border border-input bg-surface px-3 text-sm font-semibold text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <option value="base">Base model</option>
                    <option value="adapter">Fine-tuned adapter</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="validation-target" className="text-xs font-semibold text-text">
                    Target
                  </label>
                  <select
                    id="validation-target"
                    value={targetAgent ?? ''}
                    onChange={(event) => setTargetAgent(event.target.value as TargetAgent)}
                    className="h-10 w-full rounded-sm border border-input bg-surface px-3 text-sm font-semibold text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <option value="" disabled>
                      Choose an agent…
                    </option>
                    <option value="all" disabled={modelVariant === 'adapter'}>
                      All agents (SME, GAD, ITSO)
                    </option>
                    <option value="sme">SME</option>
                    <option value="gad">GAD</option>
                    <option value="itso">ITSO</option>
                  </select>
                </div>
              </div>

              {modelVariant === 'adapter' ? (
                <p className="text-xs text-text-muted">
                  The adapter is applied to one agent only, and an adapter must be loaded on the
                  server.
                </p>
              ) : null}
            </div>

```

6. Make the partial-run fieldset conditional on the all-agents target. Change its guard from `{uploadedDocumentReady ? (` to `{uploadedDocumentReady && targetAgent === 'all' ? (` (the `<fieldset ...>` that starts with `Partial validation`).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd apps/admin && npx vitest run src/features/model-validation/components/__tests__/ValidationPreparationForm.test.tsx`
Expected: PASS (existing tests plus the five new ones).

- [ ] **Step 5: Commit**

```bash
git add apps/admin/src/features/model-validation/components/ValidationPreparationForm.tsx apps/admin/src/features/model-validation/components/__tests__/ValidationPreparationForm.test.tsx
git commit -m "feat(admin): Model and Target selects on the New Benchmark Run form"
```

---

### Task 4: Frontend — remove the Compare tab and everything only it used

**Files:**
- Delete: `apps/admin/src/features/model-validation/components/AdapterComparisonForm.tsx`
- Delete: `apps/admin/src/features/model-validation/hooks/useAdapterComparisonFormState.ts`
- Delete: `apps/admin/src/features/model-validation/components/__tests__/AdapterComparisonForm.test.tsx`
- Delete: `apps/admin/src/features/model-validation/hooks/__tests__/useAdapterComparisonFormState.test.tsx`
- Modify: `apps/admin/src/features/model-validation/pages/ModelValidationPage.tsx`
- Test: `apps/admin/src/features/model-validation/pages/__tests__/ModelValidationPage.test.tsx`

**Interfaces:**
- Produces: `ValidationTab = 'history' | 'analytics' | 'new-run'`.

- [ ] **Step 1: Replace the Compare page test with the new expectations (failing)**

In `pages/__tests__/ModelValidationPage.test.tsx`, replace the whole `it('shows the Compare tab and renders the AdapterComparisonForm when selected', ...)` block with:

```tsx
  it('has no Compare tab any more', () => {
    vi.spyOn(queriesModule, 'useModelValidationHistory').mockReturnValue({
      data: mockHistoryData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<ModelValidationListResponse>);

    vi.spyOn(queriesModule, 'useModelValidationMetrics').mockReturnValue({
      data: mockMetricsData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<ModelValidationMetricsResponse>);

    renderPage();

    expect(screen.getAllByRole('tab')).toHaveLength(3);
    expect(screen.queryByRole('tab', { name: /Compare/i })).toBeNull();
  });

  it('shows the Model and Target controls and in-flight progress under New Benchmark Run', () => {
    const inFlightHistoryData: ModelValidationListResponse = {
      items: [
        {
          ...mockHistoryData.items[0],
          validation_id: 'val-2',
          status: 'EVALUATING',
        },
      ],
      total: 1,
    };

    vi.spyOn(queriesModule, 'useModelValidationHistory').mockReturnValue({
      data: inFlightHistoryData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<ModelValidationListResponse>);

    vi.spyOn(queriesModule, 'useModelValidationMetrics').mockReturnValue({
      data: mockMetricsData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<ModelValidationMetricsResponse>);

    renderPage();
    fireEvent.click(screen.getByRole('tab', { name: /New Benchmark Run/i }));

    expect(screen.getByLabelText('Model')).toBeDefined();
    expect(screen.getByLabelText('Target')).toBeDefined();
    expect(screen.getByLabelText(/Agent progress for/i)).toBeDefined();
  });
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/admin && npx vitest run src/features/model-validation/pages`
Expected: FAIL (`has no Compare tab any more` finds four tabs).

- [ ] **Step 3: Remove the Compare UI**

Delete the four files listed above with `git rm`:

```bash
git rm apps/admin/src/features/model-validation/components/AdapterComparisonForm.tsx apps/admin/src/features/model-validation/hooks/useAdapterComparisonFormState.ts apps/admin/src/features/model-validation/components/__tests__/AdapterComparisonForm.test.tsx apps/admin/src/features/model-validation/hooks/__tests__/useAdapterComparisonFormState.test.tsx
```

In `ModelValidationPage.tsx`:

1. Remove `ArrowsLeftRight,` from the `@phosphor-icons/react` import.
2. Remove the imports of `AdapterComparisonForm` and `useAdapterComparisonFormState`.
3. Change the tab type: `export type ValidationTab = 'history' | 'analytics' | 'new-run';`
4. Remove the line `const compareFormState = useAdapterComparisonFormState();`.
5. Delete the whole Compare tab `<button ...>` (the one with `aria-selected={activeTab === 'compare'}` and the `<span>Compare</span>` label).
6. Delete the whole `{activeTab === 'compare' && ( ... )}` panel at the bottom of the component.

- [ ] **Step 4: Run to verify it passes, and that nothing else referenced the removed code**

Run: `cd apps/admin && npx tsc --noEmit`
Expected: no errors.

Run: `cd apps/admin && npx eslint src/features/model-validation`
Expected: no problems.

Run: `cd apps/admin && npx vitest run src/features/model-validation`
Expected: all pass.

Run (Grep tool): search `apps` for `AdapterComparison|compareAdapter|useAdapterComparisonFormState|activeTab === 'compare'` in `*.ts`/`*.tsx`/`*.py`.
Expected: no matches.

- [ ] **Step 5: Commit**

```bash
git add -A apps/admin/src/features/model-validation
git commit -m "feat(admin): remove the Compare tab, form and hook"
```

---

### Task 5: Docs sweep and full verification

**Files:**
- Modify: any markdown under `docs/`, `training/`, or the repo root that still describes the Compare tab or the compare endpoint (found in Step 1).

- [ ] **Step 1: Find stale references**

Run (Grep tool, case-insensitive, `*.md`): pattern `compare tab|compare base|base vs adapter|model-validations/compare|compare_group_id|paired run` over `docs`, `training`, `README.md`, `apps/server/scripts`.
Expected: a short list of files. Do **not** edit the two spec files (`2026-09-23-model-validation-adapter-compare-design.md`, and this change's spec) or their plans: they are historical records of what was decided at the time.

- [ ] **Step 2: Update the live docs**

For each remaining match in operational docs (for example `training/evaluating-an-adapter.md` or a runbook), replace "use the Compare tab" with "on **+ New Benchmark Run**, choose Model = Fine-tuned adapter and a single Target agent; run once with Base and once with the adapter and compare the two history rows". If a doc mentions `compare_group_id` as something users see, say new runs no longer set it. If Step 1 finds nothing in operational docs, record that in the commit message and move on.

- [ ] **Step 3: Full backend verification**

Run: `cd apps && uv run --project server ruff check server/modules/admin server/tests/admin && uv run --project server ruff format --check server/modules/admin server/tests/admin`
Expected: clean.

Run: `cd apps && uv run --project server pytest server/tests/admin server/tests/evaluations server/tests/core server/tests/migrations server/tests/agents/supervision -q`
Expected: all pass.

- [ ] **Step 4: Full frontend verification**

Run: `cd apps/admin && npx tsc --noEmit && npx eslint src/features/model-validation && npx vitest run`
Expected: type check and lint clean; the whole admin suite passes.

- [ ] **Step 5: Manual check against the real host**

With the dev servers running and an adapter loaded on the host: on **+ New Benchmark Run**, run once with Model = Base model, Target = SME and once with Model = Fine-tuned adapter, Target = SME, on the same document with the same expected scores. Confirm: two history rows, badges Base and Adapter, the adapter row shows the adapter applied (as the Compare live test did), and choosing Adapter greys out "All agents". Then, with the adapter unloaded, confirm an Adapter submit shows "no adapter is loaded..." and a Base submit still works.

- [ ] **Step 6: Commit**

```bash
git add -A docs training README.md
git commit -m "docs: point Compare-tab instructions at the Model and Target selects"
```

(If Steps 1-2 changed nothing, skip this commit.)
