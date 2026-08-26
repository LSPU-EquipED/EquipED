## Context

GAD currently runs five sequential criterion-specific extraction calls inside one supervisor-dispatched agent. Each call receives a separate hard-coded prompt, produces an independently variable interpretation, and feeds the deterministic GAD registry. Recent production runs show this path taking about 104–148 seconds, dominating otherwise parallel evaluations.

The intended architecture is one GAD agent under the supervisor's outer parallelism. The system must retain the current official criterion coverage, deterministic score-band mapping, chunk grounding, standard agent-result shape, and honest partial-evaluation behavior.

## Goals / Non-Goals

**Goals:**
- Make one normal-path GAD LLM extraction call for all five criteria.
- Keep final numeric GAD scoring deterministic and registry-owned.
- Retain per-criterion evidence validation against the frozen SLM context.
- Preserve existing GAD output and synthesis compatibility.
- Make malformed output bounded and observable rather than silently falling back to five calls.

**Non-Goals:**
- Changing GAD's official rubric, score bands, aggregation weight, or client presentation.
- Parallelizing criterion-level calls inside GAD.
- Changing the GAD model, enabling/disabling model reasoning, or adding a new dependency in this change.
- Reusing Coordinator/SME extraction facts; GAD criteria require distinct evidence.

## Decisions

### One combined fact-extraction envelope

The GAD agent SHALL build one combined, versioned prompt through a GAD-local pipeline that reuses BaseAgent packing, model-routing, fallback, and transport helpers. It SHALL not inherit BaseAgent's score-shaped prompt or parser. Its response SHALL be a duplicate-safe ordered list with exactly one factual section for every GAD criterion. The model extracts observations and candidate evidence only; it does not assign final 1–4 scores.

This replaces five independent calls without collapsing the five criteria into one undifferentiated judgment. The managed GAD prompt SHALL be revised to fact-only instructions in this change. The final ordered, packed SLM chunks sent to the model are frozen as the only factual source; rubric and managed-prompt text are instructions, and syllabus/curriculum reference context is excluded from extraction facts.

Alternative considered: retain five calls and set Qwen reasoning effort to `none`. This can reduce latency but leaves nested orchestration and independently drifting model facts intact, so it is excluded as the primary solution.

### Preserve deterministic registry scoring

The existing GAD criterion registry remains the sole owner of final numeric score bands. The combined envelope is deliberately heterogeneous so it matches current registry inputs: GAD-01/03/04/05 require non-negative `instance_count`, an explicit instances list with exact excerpts and candidate chunk identifiers, and a non-empty summary; GAD-02 requires non-negative `female_count`/`male_count` and a non-empty summary. All five sections are validated before any scorer runs. The combined response rejects numeric-score fields, subtotals, and equivalents.

The extraction-schema version and scoring-registry version are explicit constants. This preserves institutional scoring logic while making the model's role limited and auditable.

Alternative considered: restore the earlier single model-scored GAD response. It is faster but regresses the deterministic score-band and grounding improvements, so it is rejected.

### Ground facts before scoring

For GAD-01/03/04/05, candidate excerpts and identifiers SHALL be validated against the ordered, frozen GAD context before any registry scorer runs. Unknown identifiers, malformed references, duplicate normalized excerpts, and excerpts absent from their cited chunk SHALL not become accepted evidence. GAD-02 remains count-based in this change; adding representation-instance grounding is explicitly out of scope.

If all candidate excerpts are rejected, the registry SHALL retain its current zero-accepted-instance semantics and provenance SHALL record grounding degradation. Missing evidence SHALL be represented honestly according to existing criterion rules; absence is not automatically a compliance violation.

### Bounded failure behavior

Malformed, duplicate, missing, or field-invalid combined output uses one GAD-specific whole-envelope repair call from the same frozen context. The repair prompt requests the complete fact-only envelope and never numeric scores. Evidence grounding rejection and deterministic scorer failures are not repairable. If required criterion sections remain invalid after repair, GAD SHALL return one failed result with actual elapsed timing, known model attribution, prompt version, and bounded runtime provenance; normal synthesis partial-result handling applies. The normal path SHALL not issue per-criterion fallback calls.

This favors honest partial results over hidden latency and inconsistent mixed-call outputs.

### Isolate model-routing changes

The first implementation keeps current GAD model and reasoning configuration unchanged so benchmark results isolate the extraction-topology change. It explicitly preserves `temperature=0.0`, enforces final serialized prompt-budget compliance before transport, and records bounded scalar extraction/grounding counters through the provenance sanitizer allowlist. Any later `reasoning_effort` or model-routing adjustment must be benchmarked and proposed separately.

## Risks / Trade-offs

- **A combined prompt can overlook a criterion-specific detail** → Require named per-criterion schema sections, criterion-specific extraction instructions, and human comparison on representative SLMs before rollout.
- **One malformed response affects all five criteria** → Use bounded repair, clear GAD failure attribution, and existing synthesis normalization rather than hidden fallbacks.
- **The combined response can exceed output limits** → Keep output factual and bounded; reject prose recommendations, cap evidence entries without truncating below score-band saturation thresholds, and assert serialized prompt-budget compliance before transport.
- **Equivalent fact coverage may differ from five focused prompts** → Benchmark current and proposed outputs against human review; do not use aggregate score alone as acceptance evidence.

## Migration Plan

1. Add fixed-response and grounding tests for the single-pass contract.
2. Implement the new extraction adapter, fact-only managed prompt revision, and GAD-local repair path while retaining the registry and standard result schema.
3. Run controlled comparison on representative SLMs and record GAD runtime, criterion coverage, evidence quality, and final scores for human review.
4. Deploy normally after acceptance; no data migration is required.
5. Roll back by restoring the prior GAD extraction implementation if benchmarked coverage is unacceptable.

## Open Questions

- What representative SLM set and human reviewer define acceptable criterion coverage for the comparison?
