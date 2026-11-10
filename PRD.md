# EquipED requirements

[Product scope](PRODUCT.md) defines the users and institutional purpose;
[architecture](ARCHITECTURE.md) defines the system boundaries.

## Outcomes

- Reduce repetitive preparation and recordkeeping during institutional review.
- Apply institutional rubrics with inspectable evidence and traceable feedback.
- Preserve ownership isolation, saved history, and human approval authority.

Expert agreement and review-time reductions require measured comparisons with
human-reviewed materials. The research target of at least 90% precision, recall,
and accuracy is a validation target, not a demonstrated product guarantee.

## Documents and access

| Area | Requirement |
| --- | --- |
| Accounts | Authenticate faculty and administrators; enforce account status and specialist permissions. |
| Ownership | Faculty access their own documents and evaluations. Administrative access follows server authorization. |
| Intake | Accept PDF SLMs, extract selectable text, use configured OCR, and retain source/page identities. |
| Readiness | Block unfinished or failed extraction; disclose retained warnings and review limits. |
| References | Administrators manage curricula, syllabi, rubrics, and policies. Reference readiness includes successful vector writes. |
| Programs | Accept BSCS and BSInfoTech on current writes; preserve supported legacy aliases on reads. |
| Privacy | Require privacy-appropriate source preparation and anonymization before ingestion; extraction does not perform this automatically. |

## Evaluation

Faculty select an owned processed SLM, a permitted specialist, a confirmed
program, and required references. The server validates admission and freezes the
rubric. A durable job executes the selected specialist, saves validated output,
and deterministically updates the monitoring matrix.

Coordinator requires a ready same-program curriculum. ITSO requires enabled
public-reference tools and at least one usable retrieved source passage. A
missing syllabus does not make a successful selected-specialist job partial.
Unhandled failures remain failed. Intentional no-curriculum partial bundles are
limited to explicitly supported administrative or historical workflows.

| Specialist | Required output |
| --- | --- |
| SME | Rubric scores and findings with exact evidence, or supported absence findings scoped to supplied text. |
| Coordinator | Ten LLM-scored organization/presentation and assessment criteria, complete findings and summary, plus a separate qualitative curriculum-alignment supplement. Invalid output after bounded repair fails the run. |
| GAD | Gender and inclusivity findings using the configured evidence and scoring rules. |
| ITSO | Five advisory scores with source checks, source links/passages, and coverage limits, covering citation, ownership, confidentiality, and teacher/student rights. |

Evidence must be traceable to supplied sources. Absence findings do not establish
absence from omitted text or images. ITSO distinguishes topical context from
verification of an existing citation and uncertainty from noncompliance.

## Scoring and reporting

Use the institutional 1–4 scale and saved rubric descriptors. Standard printed
bands are 3.50–4.00 Very Satisfactory, 2.50–3.49 Satisfactory, 1.50–2.49 Needs
Improvement, and 1.00–1.49 Poor.

Each specialist's score is its criterion mean. The completed matrix weights SME
35%, Coordinator 30%, GAD 20%, and ITSO 15%. Withhold the composite until all four
domains complete. Coordinator's curriculum supplement is excluded from the
official mean, composite, and institutional scorecard PDF.

Preserve each run's rubric, evidence, and provenance. Re-evaluation creates a new
run; historical formats retain their original interpretation. Retired formats do
not authorize new execution. Institutional exports preserve the original forms
and human signature fields. Missing or invalid scores stay blank; totals require
complete, correctly matched criteria.

## Feedback and administration

Faculty may submit criterion feedback on evaluations they submitted.
Administrators may review across users and inspect preference logs. Record actor,
criterion, original generation, action, and correction separately from generated
scores and institutional approval.

Administrators maintain rubric revisions, references, accounts, model settings,
and structured curriculum objectives and course mappings. Objective/mapping
changes are version-checked and actor-attributed. Saved alignment results retain
the reference versions used. Prompt configurations and history remain
backend-managed; there is no administrator prompt-editing workspace.

Training preserves dataset identity, provenance, and synthetic-versus-human
labels. Adapter upload and validation do not imply activation or improvement.

## Standalone alignment

Syllabus checks compare an owned SLM with an explicitly selected ready syllabus.
Curriculum checks use a same-program course's mapped objectives; missing mappings
block the check. These workflows remain separate from specialist matrix scoring.

## Operating requirements

- Support English and Filipino with configured OCR resources.
- Keep authenticated access, ownership isolation, and explicit external-data authorization.
- Recover relational records, document binaries, and vectors as separate assets.
- Use a single-process backend with durable in-process admission and recovery.
- Show actual stages and failures without invented progress or latency guarantees.
- Keep evidence inspectable, controls keyboard-accessible, and status understandable without color alone.
- Keep all generated evaluation and alignment results advisory.
