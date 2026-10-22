# Product

## Register

product

## Users
* **LSPU SCC Faculty Members**: Instructors submitting Self-Paced Learning Materials (SLMs) for initial automated evaluation, checking flagged text segments, and reviewing criteria scores to guide syllabus/module alignment revisions.
* **CID (Curriculum Instruction Development) Staff & Admin**: Institutional Quality Assurance reviewers who manage system-wide prompts, monitor evaluations across academic programs (BSIT, BSCS, BSIS), validate agent scorecards, and provide authoritative human decisions.

## Product Purpose
To automate the initial quality-assurance review layer of Self-Paced Learning Modules (SLMs) against institutional rubrics across four independent domains (SME content accuracy, Coordinator objective gauging (A-05) and supplemental curriculum alignment (C-01), GAD gender sensitivity, and ITSO IP compliance). The system serves as an advisory co-pilot that aggregates evaluation scores and compliance flags under the authoritative review of human CID experts.

## Brand Personality
* **Institutional**: Academic, formal, professional, and highly structured, reflecting official Laguna State Polytechnic University guidelines.
* **Authoritative & Trustworthy**: Clear, precise, and transparent about data residency, grounding sources, and evaluation limits.
* **Academic-Tech**: A clean, balanced synthesis of educational administration standards and modern natural language processing workspace features.

## Account Administration
The user-management directory excludes the signed-in administrator from its records and counts. Administrators cannot deactivate or permanently delete their own account through the administrative delete endpoints. Permanent deletion in the interface requires typing the selected account's email before confirmation.

## ITSO tool-assisted rubric evaluation

ITSO evaluates the five institutional criteria and returns advisory 1–4 scores, reasoning, grounded SLM quotations and recommendations through the same evaluation and result UI as the other specialists. The uploaded module is the direct input. Faculty select the module, confirm the program and start the evaluation; no separate source-preparation, policy-approval, attachment or fact-adjudication workflow is required.

ITSO findings contain brief, plain-language conclusions. Source links and retrieved page passages are separate supporting evidence, with readable verification limits rather than technical receipts inside the justification. The specialist summary reports measured public-reference and extracted-text review coverage and its limits; original model summaries and complete tool reports remain in captured audit responses. Frozen-rule confidentiality findings with no detected concern and provisional rights findings receive specific labels instead of a generic request for quotation evidence. Rights remain unverified, and a scoped confidentiality finding does not establish whole-module clearance. The same presentation applies to saved adapter-3 results without changing stored scores or audit flags.

Public-reference retrieval tries the citation metadata first and, when no usable source is found, one distinct title-only query. Both attempts use the same public search provider, bounded reference count and overall time limit. Search results alone never qualify as source evidence; a relevant passage must be retrieved from a source page. Aggregate retrieval diagnostics exclude module text, queries, source URLs and passages.

ITSO document review uses validated advisory source findings from criteria 1–2 to inform faculty ownership, without treating source similarity, citation, or absence of a plagiarism finding as proof of ownership or permission. Criteria 3–5 have explicit relational scoring rules and four score descriptors. Decisive ownership/rights findings require a verbatim module quotation; incomplete evidence without a concrete concern supports provisional 3. Confidentiality scores below 4 require a quoted concern; no detected concern receives advisory 4 even with limited extracted-text coverage. The scorecard states actual reviewed excerpt coverage and excludes images and extraction omissions from its assurance. Teacher/student rights assess credit, permitted educational use, authorization or lawful basis for publication, and unfair waivers. Existing ingested local IP, privacy and academic-rights policies may support this review through the existing residency-gated retrieval path. Unavailable policy evidence is a disclosed limitation, not noncompliance or a launch prerequisite. Policy passages never enter public search queries. No additional workflow, model request group or evaluation layer is introduced.

Every new ITSO evaluation requires online cross-checking for criteria 1 and 2. Credential-free public search retrieves available bounded source passages and records matches, mismatches, unavailable sources and coverage limits for the rubric evaluation. Queries use public bibliographic details, including named works listed under Learning resources. Hyperlinks are optional; criterion 2 evaluates acknowledgement and identifiable source metadata using the active relational rubric. When no safely identifiable citations are detected, searches use explicitly labelled lesson/topic names and report missing citations; topical matches do not verify attribution. Private body passages and personal information are not search queries. External access must be enabled in the server configuration, with no search-provider API key required. Required tool failures fail execution; a module without either safely extractable references or public lesson/topic names cannot complete verification. Completion also requires at least one usable public source passage. The model must cite a retrieved source in criteria 1 and 2 and explicitly report a bibliography that was not detected; one bounded repair is allowed before a response that omits these requirements fails. Bounded source links, retrieved passages and coverage limits are preserved in the existing criterion reasoning independently of model omissions; the captured request retains the complete bounded tool report; unsuccessful page attempts are recorded without fabricating matches. There is no local-only evaluation option. Retrieved sources are untrusted evidence, and source matching does not establish exhaustive plagiarism coverage or institutional approval.

Content warnings on a successfully processed SLM remain visible and do not block ITSO evaluation. Failed or unfinished extraction remains ineligible. Retired ITSO harness versions cannot execute new evaluations. Historical evidence-only adapter-2 records retain their saved evidence and withheld scores, while new scored evaluations use an explicit history-preserving rubric revision. Human review remains authoritative.

## Reviewed DPO training sources

An active, approved administrator can import a reviewed frozen DPO package through the local administrative script and select it as one agent's training source. The existing Admin readiness and Start Training Run workflow use that exact package, including its evidence and reasoning, until the administrator restores feedback export or selects another package. Historical feedback, evaluations, training jobs and fine-tuned models remain available. Package checks validate identity, hashes and provenance; they do not certify synthetic corrections as faculty judgments. Invalid active packages fail explicitly rather than silently selecting different data.

## Model Validation

Fine-Tuning Results preserves curated research snapshots for SME fine-tuned models v7, v9, and v13 and GAD v5 independently of live validation rows and model availability. Administrators can inspect synthetic-reference scores, captured evidence and reasoning, training measurements, limitations, and run provenance, and export each experiment as JSON. GAD v5 retains all eight held-out synthetic comparisons and highlights exact quotation grounding (33/40 to 39/40), separately from scoring accuracy (MAE 0.625 to 0.650; exact matches 25/40 for both). Grounding checks verbatim occurrence in the cited source chunk, not semantic relevance or correctness. Historical experiments without grounding audits do not receive reconstructed metrics. Archived excerpts are served through an authenticated administrator endpoint, never public frontend assets. The archive distinguishes training-objective progress from generated scoring accuracy and does not establish expert agreement or generalization.

The Fine-Tuning Results workspace groups archived experiments by SME, GAD, Coordinator, and ITSO. Every available experiment presents scoring accuracy, evidence quality, and reasoning quality together. Existing score metrics and quotation audits are reused; evidence relevance and reasoning quality remain explicitly unassessed until a structured review is archived. Agents without archived experiments show an empty state rather than inferred results.

## SME absence findings

For rubric-guidance criteria, SME can explicitly report required content as absent from the supplied source text, with a required explanation and no evidence quotation or document highlight. The result labels this finding “Not found in the supplied source text”; it does not establish absence from omitted portions of the SLM. Scores still follow the saved rubric. Findings that quote present content continue to require verbatim source evidence, and historical response shapes remain supported.

SME prepares oversized source inputs using local section and task-pattern hints, guided by the frozen rubric's descriptions, guidance, and level descriptors rather than fixed criterion codes or page numbers. It preserves original passages in source order, prioritizes relevant objectives, tasks, assessments, and rubrics, and keeps unfamiliar content eligible through rubric-vocabulary matching or distributed fallback passages. Cover information is deprioritized unless relevant. The existing prompt and request-count limits remain in force; selected passages do not establish complete-document coverage. This preparation introduces no model requests, SLM vector storage, or database schema changes and does not modify the other specialists.

## Anti-references
* **Generic SaaS Templates**: Avoid low-contrast gray text on near-white backgrounds, huge spacious pads, floating ghost cards, decorative background stripes, and generic dashboard marketing widgets.
* **External Component Libraries**: Absolutely no dependencies on shadcn/ui or external template kits. Every component is custom-crafted to serve dense, high-contrast academic reviews.
* **Obfuscated Logic**: Avoid hiding evaluation rationales, raw score weights, or retrieval source matches.

## Design Principles
* **Readability First**: Strictly enforce high-contrast ratios (minimum 4.5:1 for body and placeholders) using robust, accessible text sizing, readable fonts, and comfortable line-heights for prose reviews.
* **Expert Density**: Prioritize clean, compact interfaces maximizing side-by-side comparative views (e.g., document chunks next to domain scorecards) to reduce view-switching and scroll fatigue.
* **Human-in-the-Loop Clarity**: Explicitly demarcate LLM-generated outputs as *advisory only* using clear visual labels, and require direct human actions (e.g., preference logs, validation buttons) for final CID submission approval.

## Accessibility & Inclusion
* **WCAG 2.1 AA Compliance**: Strict color contrast, focus indicators on all interactive elements, keyboard-navigable dialogs, and clear aria roles.
* **Reduced Motion Respect**: Disable all complex animations and replace with immediate or basic opacity transitions when `@media (prefers-reduced-motion: reduce)` is active.

## Faculty module storage and evaluation

Module Library stores owned SLMs and exposes document details and original PDFs. Evaluation status, launch, progress, result inspection, and retry belong to the permitted specialist workspace, where status is specific to that specialist. Module Library does not summarize the latest specialist job as overall module completion.

Faculty evaluation results use a consistent presentation across specialist workspaces and Evaluation History. An opened result remains tied to one evaluation run, including its evidence, rubric snapshot, reviewer corrections, and PDF export. Re-evaluation creates a new run rather than replacing the earlier record. Specialist completion and score review do not constitute institutional approval.

## Curriculum alignment response reliability

Standalone curriculum alignment places JSON output rules in a system message and module content and objectives in a separate untrusted user data block. It requests a structured response covering every mapped objective using the configured model response format: JSON-object mode by default, or an explicit objective schema when JSON-schema mode is enabled for a compatible server. A complete Markdown JSON wrapper and a top-level array of objective results are normalized before the same strict validation; invalid fields, missing or duplicate objectives, and truncated output still fail the whole check. Output space scales with the number of objectives within a fixed upper bound. A model output-limit failure receives a specific explanation. Provenance retains safe completion metadata, the original top-level JSON type, wrapper normalization flags, and bounded validation errors without raw responses, module text, or untrusted field names and objective codes. The existing single-call workflow and one transient retry remain unchanged, with no automatic model fallback or response-repair calls.
