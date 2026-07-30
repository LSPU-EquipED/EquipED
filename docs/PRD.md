# EquipEd PRD
## A Multi-Agent SLM Evaluation System for Quality Assurance using NLP

**Institution:** Laguna State Polytechnic University – Santa Cruz Campus, College of Computer Studies  
**Proponents:** Alberto, Marc Justin G. · Aquino, Jose V. III · Garin, Jeremy M.  
**Version:** 0.3 | **Status:** `DRAFT — Pending Data Completion`

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Goals & Success Metrics](#2-goals--success-metrics)
3. [Users & Roles](#3-users--roles)
4. [System Scope](#4-system-scope)
5. [Deliverables](#5-deliverables)
6. [Functional Requirements](#6-functional-requirements)
7. [Non-Functional Requirements](#7-non-functional-requirements)
8. [Data Requirements](#8-data-requirements)
9. [Evaluation Criteria & Rubrics](#9-evaluation-criteria--rubrics)
10. [Use Cases](#10-use-cases)
11. [Assumptions & Constraints](#11-assumptions--constraints)
12. [Open Items](#12-open-items)

---

## 1. Problem Statement

The Curriculum Instruction Development (CID) Office at LSPU SCC evaluates Self-Paced Learning Modules (SLMs) manually through four institutional units: Subject Matter Experts (SME), Program Coordinators, the Gender and Development (GAD) Unit, and the Innovation and Technology Support Office (ITSO). Each unit reviews modules independently against their own rubric criteria.

This process has three compounding problems:

**Inefficiency.** Each module requires independent review by multiple evaluators. As the volume of SLMs across academic programs grows, the manual workload creates backlogs in the CID Office.

**Inconsistency.** Different evaluators interpret rubric criteria differently, producing variable scores for materially similar content.

**Limited traceability.** There is no centralized system for tracking evaluation status, scores, or feedback history across the full SLM inventory.

EquipEd addresses these problems by automating the initial evaluation layer — analyzing SLMs against institutional rubric criteria and generating structured feedback — while preserving human evaluator authority over final decisions.

---

## 2. Goals & Success Metrics

### 2.1 Goals

| # | Goal |
|---|---|
| G-01 | Automate rubric-based SLM evaluation across all four institutional stakeholder perspectives |
| G-02 | Ground all evaluation feedback in institutional reference documents (syllabi, curriculum guides, rubrics) |
| G-03 | Generate a consolidated scorecard and flagged document highlights per evaluated SLM |
| G-04 | Capture evaluator feedback and use it to progressively improve evaluation accuracy over time |
| G-05 | Provide a centralized web interface for document submission, evaluation results, and evaluation history |

### 2.2 Success Metrics

| Metric | Target | Measurement Method |
|---|---|---|
| Evaluation agreement with human experts | ≥ 90% precision, recall, and accuracy | Validated against expert-reviewed SLMs from the LSPU SCC corpus |
| Reduction in manual evaluation time | Measurable reduction vs. baseline | Time study comparing manual vs. system-assisted evaluation cycles |
| Rubric coverage | 100% of evaluation criteria across all four rubrics addressed | Rubric mapping verification against system outputs |
| Evaluator feedback incorporation | System prompt refinements traceable to logged preference data | Version history of agent prompts vs. preference log entries |

---

## 3. Users & Roles

### 3.1 Human System Roles

| Role | Description | System Access |
|---|---|---|
| **Faculty Member** | Submits SLMs for evaluation; reviews flagged sections and scores to guide revisions | Upload SLMs; view own evaluation results and feedback |
| **Admin / CID Staff** | Manages the system, reviews evaluator feedback, validates agent-generated outputs, updates agent configurations, monitors the full evaluation inventory | Full system access including evaluation history, preference logs, prompt management, and monitoring matrix |

### 3.2 Evaluator Agent Domains

The system includes four internal evaluator subagents that operate on institutional rubric domains. These are **not human login roles** but rather **automated agent domains** that generate evaluation perspectives:

| Agent Domain | Institutional Stakeholder | Evaluation Focus |
|---|---|---|
| **SME** | Subject Matter Expert | Content accuracy, coherence, and instructional organization |
| **Coordinator** | Program Coordinator | Curriculum alignment and OBE compliance |
| **GAD** | Gender and Development Unit | Gender sensitivity and inclusivity |
| **ITSO** | Innovation and Technology Support Office | IP compliance and data privacy |

**Terminology Note:** "Evaluator" in this document refers to the automated agent domains (SME, Coordinator, GAD, ITSO) unless explicitly qualified as "human evaluator" or "admin user." Human system roles are limited to Faculty Member and Admin / CID Staff (Section 3.1).

**Note:** Admin users review and validate all agent-generated outputs. Feedback submitted by admin users on agent outputs is logged for iterative prompt refinement. Faculty members may view evaluation results but do not submit formal feedback on agent outputs.

---

## 4. System Scope

### 4.1 Academic & Program Scope

The system is deployed for **Laguna State Polytechnic University – Santa Cruz Campus (LSPU SCC)** within the **College of Computer Studies (CCS)**. Current product scope supports the following canonical degree programs:
- **`BSInfoTech`** (Bachelor of Science in Information Technology) — *Note: `BSIT` is explicitly not used as the canonical code to prevent ambiguity with Industrial Technology.*
- **`BSCS`** (Bachelor of Science in Computer Science)

Other academic departments and campuses within LSPU SCC are explicitly designated for future institutional expansion.

### 4.2 In Scope

- **Document Processing:** Processing of CCS SLMs (submitted as PDF documents), CCS curriculum guides, and LSPU CCS syllabi, alongside institutional evaluation rubrics.
- **Evaluation Domains:** Automated evaluation across four stakeholder rubric domains: Organization & Presentation (SME), Assessment (SME), Curriculum Alignment & OBE (Program Coordinator), Inclusivity & Gender Sensitivity (GAD Unit), and IP & Data Privacy (ITSO).
- **Evaluation Modes:**
  - **Full Syllabus-Aware Evaluation:** Requires an authoritative LSPU CCS course syllabus to evaluate alignment with course learning outcomes and curriculum objectives.
  - **Deliberate Partial Evaluation:** When an authoritative syllabus is absent, faculty may deliberately choose to continue a clearly marked partial evaluation. A missing syllabus does not silently remain a full curriculum-only evaluation.
- **Outputs & Management:** Generation of rubric-based scores, contextual document highlights, consolidated evaluation reports (D-03), web dashboard (D-05), and an Instructional Materials Monitoring Matrix (D-04).
- **Feedback & Optimization:** Admin-only preference logging mechanism (D-06) capturing Accept / Reject / Edit feedback on agent outputs to support iterative prompt updates.

### 4.3 Reference Authority & Calibration Policy

- **Authoritative Reference Data:** Official LSPU CCS syllabi, curriculum guides, and institutional rubrics are the sole authoritative sources for live evaluation evidence.
- **Secondary Calibration Materials:** Publicly accessible curriculum or benchmark materials from other Philippine state universities serve strictly as secondary calibration materials for offline prompt tuning and benchmark alignment. They shall never serve as live evaluation retrieval evidence. Private university materials are explicitly excluded from this calibration source policy.
- **Historical SLM Calibration Corpus:** Historical SLMs may only be used as an admin-only, de-identified calibration corpus paired with recorded human-reviewed outcomes for model/prompt calibration. They shall never be ingested or retrieved as live evaluation evidence.

### 4.4 Out of Scope

- Evaluation of instructional materials other than SLMs (e.g., textbooks, slide decks, video content).
- Evaluation of programs, courses, or departments outside the LSPU SCC College of Computer Studies (CCS).
- Evaluation based on rubrics or standards from institutions other than LSPU SCC.
- Live retrieval or inclusion of secondary external materials (from other state universities) or historical SLMs during live SLM evaluations.
- Automatic generation of revised or corrected SLM content.
- Real-time collaborative review between multiple evaluators on the same session.
- Processing of SLM content written in languages other than English and Filipino.

### 4.5 Future Scope & Expansion

The following capabilities are identified as governed future expansion directions and are **not currently implemented**:
- **Institutional Expansion:** Expanding scope to other LSPU SCC academic departments and campuses beyond the College of Computer Studies.
- **Governed Calibration Corpus:** Implementation of the admin-only, de-identified historical SLM calibration dataset with recorded human-reviewed outcomes.
- **Secondary Source Ingestion Pipeline:** Automated ingestion and management of external secondary calibration materials from other Philippine state universities.

---

## 5. Deliverables

These are the concrete outputs the system must produce. Each deliverable is referenced by functional requirements in Section 6.

### D-01 — Consolidated Evaluation Scorecard

A structured scorecard produced per evaluated SLM containing:

- Per-criterion scores from each of the four rubric domains, on the institutional 4-point scale (4 = Excellent, 3 = Satisfactory, 2 = Needs Improvement, 1 = Poor)
- Per-domain subtotals and an aggregate evaluation total
- Identification of which agent (SME, Program Coordinator, GAD, ITSO) produced each score

### D-02 — Contextual Document Highlights

A set of annotated flags on the evaluated SLM identifying:

- Specific text passages or sections that deviate from evaluation criteria
- The rubric criterion violated per flag
- A brief justification for each flag grounded in the retrieved reference document context

### D-03 — Final Evaluation Report

A structured document combining D-01 and D-02, suitable for submission to the CID Office, containing:

- Cover information (SLM title, program, evaluation date, evaluator agents)
- Full scorecard (D-01)
- All contextual flags with justifications (D-02)
- An overall evaluation summary

### D-04 — Instructional Materials Monitoring Matrix

A persistent, centralized tracking record of all SLMs that have passed through the system, containing:

- SLM title and associated program
- Submission date
- Current evaluation status (Pending / Evaluated / Reviewed / Approved)
- Aggregate score and per-domain scores
- Evaluator feedback status (No feedback / Partially reviewed / Fully reviewed)

### D-05 — Web Dashboard

A browser-based interface through which all user roles interact with the system. The dashboard must surface all other deliverables (D-01 through D-04) and provide the document upload and feedback interfaces described in Section 6.

### D-06 — Preference Log & Prompt Version History

A persistent record of:

- All evaluator Accept / Reject / Edit feedback interactions with timestamps and user role
- The agent system prompt version active at the time each evaluation was generated
- A history of prompt updates with the preference data that motivated each change

---

## 6. Functional Requirements

### 6.1 Document Submission

| ID | Requirement | Deliverable | Priority |
|---|---|---|---|
| FR-01 | The system shall accept PDF uploads of SLMs via the web dashboard | D-05 | High |
| FR-02 | The system shall accept PDF uploads of course syllabi, curriculum guides, and institutional evaluation rubrics as reference documents | D-05 | High |
| FR-03 | The system shall allow a submitted SLM to be associated with its corresponding syllabus and curriculum guide at the time of upload | D-05 | High |
| FR-04 | The system shall extract machine-readable text from uploaded PDFs, including text embedded in scanned or image-based pages | D-01, D-02 | High |
| FR-05 | The system shall tag all extracted document chunks with their source type (SLM / syllabus / rubric / curriculum) to support direct SLM evaluation routing and separate retrieval scoping for reference context | D-01, D-02 | High |

### 6.2 Automated Evaluation

| ID | Requirement | Deliverable | Priority |
|---|---|---|---|
| FR-06 | The system shall evaluate each submitted SLM against the SME rubric criteria for Organization & Presentation and Assessment domains | D-01, D-02 | High |
| FR-07 | The system shall evaluate each submitted SLM against the Program Coordinator rubric criteria, verifying alignment with the associated syllabus learning outcomes and curriculum objectives | D-01, D-02 | High |
| FR-08 | The system shall evaluate each submitted SLM against the GAD Unit rubric criteria for Inclusivity & Gender Sensitivity | D-01, D-02 | High |
| FR-09 | The system shall evaluate each submitted SLM against the ITSO rubric criteria for IP compliance and Data Privacy | D-01, D-02 | High |
| FR-10 | All evaluation feedback generated by the system shall be grounded in retrieved content from the institutional reference documents (syllabi, curriculum guides, rubrics) rather than generated without retrieval context | D-02, D-03 | High |
| FR-11 | The system shall assess the sequential flow, logical organization, and instructional coherence of SLM content as part of the SME evaluation | D-01, D-02 | Medium |

### 6.3 Scoring & Report Generation

| ID | Requirement | Deliverable | Priority |
|---|---|---|---|
| FR-12 | The system shall assign a score on the institutional 4-point scale to each evaluation criterion across all four rubric domains | D-01 | High |
| FR-13 | The system shall compute per-domain subtotals and an aggregate evaluation total from individual criterion scores | D-01 | High |
| FR-14 | The system shall annotate specific SLM text passages that deviate from rubric criteria, identifying the criterion violated and providing a retrieval-grounded justification | D-02 | High |
| FR-15 | The system shall generate a final evaluation report combining the scorecard and document highlights, structured for CID submission | D-03 | High |

### 6.4 Web Dashboard

| ID | Requirement | Deliverable | Priority |
|---|---|---|---|
| FR-16 | The dashboard shall provide a document upload interface for submitting SLMs and associating reference documents | D-05 | High |
| FR-17 | The dashboard shall display the evaluation scorecard, per-agent scores, document highlights, and final report upon evaluation completion | D-05 | High |
| FR-18 | The dashboard shall indicate evaluation pipeline progress to the user while processing is underway | D-05 | Medium |
| FR-19 | The dashboard shall provide Accept, Reject, and Edit controls on each generated evaluation output, accessible exclusively to admin users for validating and refining agent outputs | D-05 | High |
| FR-20 | The dashboard shall display the Instructional Materials Monitoring Matrix exclusively to admin users | D-04, D-05 | Medium |
| FR-21 | The dashboard shall maintain a searchable evaluation history accessible to authorized users | D-04, D-05 | Medium |

### 6.5 Preference Logging & Prompt Optimization

| ID | Requirement | Deliverable | Priority |
|---|---|---|---|
| FR-22 | The system shall log all admin Accept / Reject / Edit interactions as preference records, capturing the admin user role, timestamp, agent domain, and original output | D-06 | High |
| FR-23 | The system shall version all agent evaluation prompts, associating each evaluation result with the prompt version that produced it | D-06 | Medium |
| FR-24 | The system shall provide an admin interface for reviewing accumulated preference logs and applying prompt updates based on identified patterns | D-05, D-06 | Medium |
| FR-25 | The system shall record a traceable history of prompt updates, linking each change to the preference data that motivated it | D-06 | Medium |

---

## 7. Non-Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| NFR-01 | **Accuracy.** The system shall achieve evaluation agreement with human experts of at least 90% on precision, recall, and accuracy metrics, validated against expert-reviewed SLMs from the LSPU SCC corpus. | High |
| NFR-02 | **Language Support.** The system shall correctly process SLM content written in English and Filipino. Content in other languages is out of scope and may produce inaccurate outputs. | High |
| NFR-03 | **Data Privacy.** All institutional documents processed by the system shall be handled in compliance with RA 10173 (Data Privacy Act of 2012). Personally identifiable information in uploaded documents shall be anonymized prior to processing. | High |
| NFR-04 | **Local Data Residency.** Document embedding and vector storage operations shall run on local institutional infrastructure. No raw SLM content or institutional document data shall be transmitted outside the institutional deployment boundary beyond what is strictly required for the configured local or self-hosted LLM backend. `[TBD: backend data handling policy required]` | High |
| NFR-05 | **Human Oversight.** System-generated evaluation outputs are advisory only. All outputs are subject to human evaluator review and shall not constitute official CID evaluation decisions without explicit evaluator confirmation. | High |
| NFR-06 | **Processing Time.** The system shall complete evaluation of a standard SLM (20–40 pages) within a processing window acceptable for institutional workflows. `[TBD: target to be defined upon prototype benchmarking]` | Medium |
| NFR-07 | **Maintainability.** Rubric content, agent evaluation prompts, and document preprocessing configurations shall be independently updatable without requiring full system redeployment. | Medium |
| NFR-08 | **Institutional Scope.** The system's rubric logic and knowledge base are calibrated to LSPU SCC standards. Portability to other institutions is not a design goal and is outside scope. | Medium |

---

## 8. Data Requirements

### 8.1 Required Data Sources

| Source | Role in System | Collection Status |
|---|---|---|
| Self-Paced Learning Modules (SLMs) | Primary evaluation subject; extracted chunk text is evaluated directly, with stored chunks retained for traceable retrieval support | `[TBD — In progress]` |
| SME & Program Coordinator Evaluation Rubric | Primary retrieval corpus for rubric-grounded scoring criteria in FR-06 and FR-07 | Partially collected |
| GAD Unit Evaluation Rubric | Primary retrieval corpus for rubric-grounded scoring criteria in FR-08 | Partially collected |
| ITSO Evaluation Rubric | Primary retrieval corpus for rubric-grounded scoring criteria in FR-09 | Partially collected |
| Course Syllabi | Primary retrieval corpus for syllabus alignment verification (FR-07) | `[TBD]` |
| Curriculum Guides | Primary retrieval corpus for OBE compliance verification (FR-07) | `[TBD]` |
| CID Evaluated Forms | Output structure reference for report generation; baseline for preference logging | `[TBD]` |

### 8.2 Data Constraints

- Live evaluation reference data is sourced exclusively from LSPU CCS institutional documents (syllabi, curriculum guides, rubrics).
- Public materials from other Philippine state universities may be referenced strictly for secondary prompt calibration, never as live evaluation retrieval evidence. Private university materials are excluded from calibration policy.
- Historical SLMs are restricted to an admin-only, de-identified calibration corpus with recorded human review decisions for future prompt alignment (governed future capability; not currently implemented), and are never used as live evaluation evidence.
- Documents containing personally identifiable information must be anonymized before ingestion.
- Evaluation accuracy is directly dependent on the quality and internal consistency of reference documents; incoherent or incomplete syllabi will degrade initial output reliability. Full syllabus-aware evaluation requires an authoritative LSPU CCS syllabus; when absent, deliberate partial evaluation is supported.
- The preference logging system (D-06) requires a minimum corpus of evaluator feedback interactions before prompt refinements are actionable.

---

## 9. Evaluation Criteria & Rubrics

### 9.1 Scoring Scale

| Score | Label |
|---|---|
| 4 | Excellent |
| 3 | Satisfactory |
| 2 | Needs Improvement |
| 1 | Poor |

### 9.2 Rubric Domain Coverage per Agent

| Agent | Rubric Domain | Criteria Count | Sample Criteria |
|---|---|---|---|
| SME & Program Coordinator | Organization & Presentation | 5 | Topic coherence across units; clarity of directions; accuracy of paragraphs; enhancement activities |
| SME & Program Coordinator | Assessment | 5 | Assessment variety; ongoing progress monitoring; prescriptive feedback; effective objective gauging |
| GAD Unit | Inclusivity & Gender Sensitivity | 5 | Freedom from gender stereotypes; equal representation; inclusive language; promotion of equality |
| ITSO | IP & Data Privacy | 5 | Absence of plagiarism; proper citation; faculty ownership rights; student data confidentiality |

### 9.3 Score Aggregation

Individual criterion scores within each domain are summed per rubric. The institutional aggregation formula applied across domains produces the consolidated evaluation total. The exact formula is defined in the CID rubric documents and will be implemented in the scoring layer upon full data collection.

---

## 10. Use Cases

### UC-01: Faculty Submits SLM for Evaluation

| | |
|---|---|
| **Actor** | Faculty Member |
| **Precondition** | Faculty has a completed or draft SLM in PDF format. Reference documents (syllabus, curriculum guide) are already loaded in the system. |
| **Flow** | 1. Faculty uploads SLM via the dashboard and associates it with the relevant syllabus and curriculum guide. 2. System processes the document and runs evaluation across all four agent domains. 3. Dashboard displays the consolidated scorecard (D-01), document highlights (D-02), and final report (D-03) upon completion. |
| **Postcondition** | Evaluation report is stored in the system and the SLM entry appears in the Monitoring Matrix (D-04). |
| **Exception** | If text extraction fails on one or more pages, the system flags those pages as unprocessable and proceeds with available content. |

### UC-02: Admin Validates and Submits Feedback on Generated Outputs

| | |
|---|---|
| **Actor** | Admin / CID Staff |
| **Precondition** | A completed evaluation report exists for an SLM. |
| **Flow** | 1. Admin reviews the scorecard and highlights in the dashboard. 2. For each output item, admin selects Accept, Reject, or submits an Edit with a correction. 3. System logs the interaction as a preference record in D-06, capturing the admin user role, timestamp, agent domain, and original output. |
| **Postcondition** | Preference record stored. The SLM's feedback status in the Monitoring Matrix updates accordingly. |
| **Exception** | If no feedback is submitted, the evaluation record remains unchanged and the prompt configuration is retained. |

### UC-03: Admin Reviews Preference Logs and Refines Agent Prompts

| | |
|---|---|
| **Actor** | Admin / CID Staff |
| **Precondition** | A sufficient volume of evaluator feedback has accumulated in the preference log (D-06). |
| **Flow** | 1. Admin accesses the preference review interface and filters logs by agent domain and feedback type. 2. Admin identifies patterns where a specific agent consistently diverges from evaluator judgment. 3. Admin updates the affected agent's evaluation prompt and saves the new version. 4. System records the prompt update with a link to the preference data that motivated it. |
| **Postcondition** | New prompt version is active for subsequent evaluations. Change is traceable in the prompt version history. |
| **Exception** | If the update produces worse outcomes in subsequent evaluations, the admin can revert to a prior prompt version using the version history. |

### UC-04: Admin Reviews Monitoring Matrix

| | |
|---|---|
| **Actor** | Admin / CID Staff |
| **Precondition** | One or more SLMs have been evaluated and recorded in the system. |
| **Flow** | 1. Admin opens the Monitoring Matrix view on the dashboard. 2. Admin filters the matrix by program, evaluation status, or score range. 3. Admin identifies SLMs with low scores or incomplete feedback and follows up with relevant faculty or coordinates with program coordinators. |
| **Postcondition** | No state change in the system. Admin uses the matrix as a management tool for tracking SLM review progress and institutional evaluation inventory. |

---

## 11. Assumptions & Constraints

### 11.1 Assumptions

- LSPU SCC will authorize access to fully-evaluated SLMs, syllabi, curriculum guides, and CID evaluation forms within the project timeline
- All four institutional evaluation rubrics are sufficiently documented to serve as the agent knowledge base
- Human evaluators from all four units will be available to provide feedback for preference logging
- SLM documents are submitted in PDF format; scanned documents are handled by the OCR layer
- Syllabus and curriculum documents are internally coherent; significant incoherence in source materials will reduce initial evaluation reliability

### 11.2 Constraints

| Constraint | Description |
|---|---|
| **Institutional & Departmental Scope** | System is designed exclusively for LSPU SCC College of Computer Studies (CCS) supporting canonical programs `BSInfoTech` and `BSCS`. Rubric calibration, knowledge base content, and scoring logic are specific to LSPU CCS. Other LSPU SCC departments and external institutions are outside current product scope. |
| **Language Scope** | English and Filipino only. Other languages are outside scope. |
| **Human Oversight** | System outputs are advisory. Final evaluation authority remains with institutional evaluators. System outputs do not constitute official CID decisions without evaluator confirmation. |
| **Prompt-Based Optimization** | Preference-driven improvement operates through agent prompt updates, not model weight modification. This is a constraint of the local prompt-driven LLM backend architecture. |
| **Data Completeness** | Evaluation accuracy depends on the quality of institutional reference documents. Incomplete or inconsistent source data will degrade reliability at initial deployment. |
| **LLM Backend Data Governance** | LLM calls are expected to run on a local or self-hosted backend. Compliance with RA 10173 for any model-hosting or inference path still requires confirmation from LSPU SCC institutional IT governance. `[TBD]` |

---

## 12. Open Items

| # | Item | Impact | Owner | Status |
|---|---|---|---|---|
| OI-01 | Full SLM dataset not yet collected | Blocks accuracy validation (NFR-01) and preference logging baseline | Research team | Pending institutional data request |
| OI-02 | GAD and ITSO rubrics not fully finalized | Blocks agent knowledge base population for FR-08 and FR-09 | Research team | Pending CID document release |
| OI-03 | Course syllabi not yet collected | Blocks syllabus alignment evaluation (FR-07) | Research team | Pending departmental data request |
| OI-04 | Curriculum guides not yet collected | Blocks OBE compliance evaluation (FR-07) | Research team | Pending departmental data request |
| OI-05 | CID evaluated forms not yet obtained | Blocks report structure reference and preference baseline (D-06) | Research team | Pending CID approval |
| OI-06 | Processing time target undefined | Blocks NFR-06 definition | Research team | Pending prototype benchmarking |
| OI-07 | LLM backend data handling policy not confirmed | Blocks NFR-04 and NFR-05 compliance confirmation | LSPU SCC IT / legal | Pending institutional review |
| OI-08 | Minimum feedback volume for prompt refinement not defined | Blocks FR-24 actionability threshold | Research team | Pending advisor input |

---

*LSPU SCC, College of Computer Studies*
