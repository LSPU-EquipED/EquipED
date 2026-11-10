# Evaluating an SLM

EquipED produces advisory reviews against institutional rubrics. Faculty and
institutional reviewers remain responsible for interpreting findings and making
approval decisions.

## Prepare a module

Upload an owned PDF in Module library. Processing extracts selectable text and
uses configured OCR for scanned pages. Wait for processing to finish and inspect
any content warnings. Extraction errors block evaluation; warnings and omitted
images limit what a text-based review can establish.

Confirm the module's program as BSCS or BSInfoTech. Select the specialist
workspace you are permitted to use. Coordinator also requires a ready curriculum
for the same program. A syllabus is optional for specialist submissions.

## Start and follow a run

A faculty submission runs one specialist. The server checks ownership,
permissions, source readiness, and required references, and freezes the selected
rubric for that run. Progress follows queued, preparation, specialist review, and
finalizing stages. A completed specialist job does not mean that all four domains
or institutional approval are complete.

Failed runs retain their error state. Re-evaluation creates a new record rather
than replacing the failed or completed run. Explicit administrative validation
bundles may retain intentional partial modes; normal faculty submissions do not
use those modes to recover from failures.

## How specialists use evidence

### Subject Matter Expert

SME evaluates the assigned rubric against SLM text. Oversized inputs are bounded
using section/task hints and rubric vocabulary while retaining original passages.
Quoted findings require exact source text. Supported absence findings are labelled
as not found in the supplied text and do not establish whole-document absence.

### Program Coordinator

Coordinator uses document-scoped SLM embeddings to rank exact evidence passages.
Its three model groups cover Organization & Presentation, Assessment, and a
curriculum-alignment supplement. The ten official criteria receive advisory
scores and complete findings. The supplement compares SLM and curriculum evidence
on a qualitative 1–4 scale and is excluded from the official average and PDF.

Selected passages are bounded, so the review does not claim exhaustive coverage.
Citation identifiers attach original text. Invalid findings, evidence, or summary
receive one bounded repair; unresolved output fails the run rather than returning
placeholder or partial reasoning.

### Gender and Development

GAD reviews the supplied text for gender sensitivity and inclusivity using the
saved rubric's evidence and scoring rules. Its findings and counts describe the
reviewed source; they do not certify every image or omitted passage.

### ITSO

Every new ITSO run searches public references and retrieves available source-page
passages for criteria 1 and 2. Search uses public citation metadata from sections
such as References, Bibliography, or Learning resources. Links are optional. If
safe citations are not detected, labelled lesson/topic queries provide context
and the result reports missing citations. A topic match does not verify attribution.

The server must enable reference checks with `ITSO_VERIFICATION_ENABLED=true`.
Current public search requires no API key. Queries exclude private body passages
and personal information. Search snippets alone are insufficient: at least one
usable source-page passage is required. Missing tools, unsafe execution, or no
usable retrieved evidence fails the run. Individual inaccessible references may
remain unverified with a stated coverage limit when usable evidence exists.

Five scored criteria cover source use, acknowledgement, faculty ownership,
confidentiality, and teacher/student rights. Source findings inform ownership
without proving it. Under applicable saved rules, no confidentiality concern
receives advisory 4 for reviewed text; incomplete ownership/rights evidence may
support provisional 3. Concrete adverse findings require source quotations.
Unavailable local policy evidence is disclosed rather than treated as misconduct.

## Read and review results

Results keep scores, concise findings, SLM quotations, and source checks distinct.
Inspect the evidence and any coverage or uncertainty notices before accepting a
judgment. History opens the exact saved evaluation; a workspace pins its opened
run and offers an explicit action to view a newer one.

Faculty can record criterion feedback on evaluations they submitted.
Administrators can review across users. Corrections remain separate from generated
output. Neither corrections nor a completed job constitute institutional approval.

Specialist scores are criterion means. The matrix combines SME 35%, Coordinator
30%, GAD 20%, and ITSO 15% only after all four domains complete. Until then the
matrix remains in progress without a composite.

## Export and alignment

PDF export fills the original institutional forms using the displayed saved run.
Missing scores and human signature fields remain blank. Historical scorecards
retain their saved rubric interpretation and limitations.

Syllabus check and Curriculum check are independent workflows. Select a ready
syllabus, or a same-program course with mapped curriculum objectives, respectively.
Their results do not add specialist scores to the monitoring matrix.

See [product requirements](../PRD.md), [architecture](../ARCHITECTURE.md), and
[operations](operations.md).
