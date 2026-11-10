# EquipED

EquipED supports review of Self-Paced Learning Modules (SLMs) at Laguna State
Polytechnic University – Santa Cruz Campus, College of Computer Studies. It
provides advisory rubric scores, evidence, and findings to help faculty and
Curriculum Instruction Development (CID) reviewers improve instructional materials.
Human reviewers retain authority over institutional decisions. Completed
scorecards and exported forms do not grant approval.

## Users and scope

Faculty manage their own SLMs, run permitted evaluations, inspect results, and
record score reviews. Administrators manage accounts, institutional references,
curriculum objectives, rubrics, feedback, monitoring, and model administration.
The supported programs are **BSCS** and **BSInfoTech**. English and Filipino are
the supported document languages.

## Specialist reviews

| Specialist | Purpose |
| --- | --- |
| Subject Matter Expert (SME) | Review instructional content, organization, presentation, and assessment. |
| Program Coordinator | Review organization, presentation, and assessment, with a separate curriculum-alignment supplement. |
| Gender and Development (GAD) | Review gender sensitivity, representation, and inclusive language. |
| Innovation and Technology Support Office (ITSO) | Review source use, citations, ownership, confidentiality, and teacher/student rights. |

A faculty submission runs one selected specialist. Coordinator requires a ready
curriculum for the confirmed program. ITSO requires configured public-reference
search and source-page retrieval. Other specialist jobs complete independently.
Each domain contributes to the monitoring matrix; the composite appears after
all four domains complete. Re-evaluation creates a new saved run.

## Evidence and review

The uploaded SLM is the authoritative input. Findings identify reviewed passages
where available and disclose missing evidence and coverage limits. Bounded text
selection, OCR omissions, and inaccessible sources limit what a review establishes.
Coordinator uses document-scoped SLM embeddings to select bounded evidence.
ITSO searches public citation metadata or lesson/topic names, excluding private
body passages and personal data from queries. Public matches do not establish
exhaustive plagiarism detection, ownership, or legal compliance.

Faculty can submit corrections for evaluations they submitted; administrators
can review across evaluations. Feedback remains separate from generated output
and institutional approval. Standalone syllabus and curriculum checks are
separate workflows and do not contribute specialist matrix scores.

## Information handling

Access is authenticated and ownership-scoped. Storage and inference are
local/private by default. External storage or processing requires explicit
deployment configuration and authorization. Authorized Chroma Cloud may store
institutional and document-scoped vectors with their text and metadata; this
does not authorize external inference. Policy evidence has additional residency
controls. Users must prepare documents according to institutional privacy
requirements, including anonymizing personal data before ingestion where required;
extraction is not an automatic anonymization guarantee.

## Results and model improvement

Results include rubric scores, findings, evidence, history, and institutional
PDF exports. Exports preserve supplied forms and leave unavailable scores and
human signatures blank. Administrators can prepare feedback-based or reviewed
training packages, hand off notebook training, receive adapters, and inspect
model validation. Archived research results retain their scope, provenance, and
limitations. Synthetic comparisons are not independent expert validation.

See [requirements](PRD.md), [architecture](ARCHITECTURE.md),
[evaluation](docs/evaluation.md), and [design](DESIGN.md).
