<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/branding/equiped-lspu-dark.svg" />
    <img src="assets/branding/equiped-lspu.svg" alt="EquipED × LSPU" width="560" />
  </picture>
</p>

<p align="center">
  Institutional review of self-paced learning modules<br />
  Laguna State Polytechnic University · Santa Cruz Campus · College of Computer Studies
</p>

<p align="center">
  <img src="https://img.shields.io/badge/React-18-1b3b87?style=flat-square&amp;logo=react&amp;logoColor=white" alt="React 18" />
  <img src="https://img.shields.io/badge/TypeScript-3178c6?style=flat-square&amp;logo=typescript&amp;logoColor=white" alt="TypeScript" />
  <img src="https://img.shields.io/badge/Python-3.12-3776ab?style=flat-square&amp;logo=python&amp;logoColor=white" alt="Python 3.12" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&amp;logo=fastapi&amp;logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/pnpm-9.12.0-f69220?style=flat-square&amp;logo=pnpm&amp;logoColor=white" alt="pnpm 9.12.0" />
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#common-commands">Commands</a> ·
  <a href="docs/README.md">Documentation</a> ·
  <a href="ARCHITECTURE.md">Architecture</a> ·
  <a href="DESIGN.md">Design system</a>
</p>

---

EquipED is an advisory, multi-agent evaluation system for Self-Paced Learning
Modules (SLMs) at **Laguna State Polytechnic University – Santa Cruz Campus,
College of Computer Studies**. It helps faculty and CID reviewers inspect
instructional materials against institutional rubrics and references.

The supported programs are **BSCS** and **BSInfoTech**. Generated scores,
findings, and recommendations support human review; they do not constitute
institutional approval.

## What it does

- **Module management:** upload faculty-owned PDFs, extract selectable text, and
  process scanned pages with configured English and Filipino OCR.
- **Specialist evaluation:** run one permitted specialist per faculty submission
  and inspect its saved rubric scores, findings, and supporting evidence.
- **Alignment checks:** compare modules with selected syllabi or mapped curriculum
  objectives through separate, non-scoring workspaces.
- **Review and history:** inspect exact saved runs, record criterion feedback,
  and create new evaluations while retaining previous results.
- **Monitoring and exports:** progressively fill the institutional monitoring
  matrix and export the original specialist forms and approval sheet.
- **Administration:** manage accounts, institutional references, rubric revisions,
  curriculum objectives, feedback, and model training and validation.

## Specialist reviews

| Specialist | Review focus |
| --- | --- |
| Subject Matter Expert (SME) | Instructional content, organization, presentation, and assessment. |
| Program Coordinator | Organization, presentation, and assessment, plus a separate curriculum-alignment supplement. |
| Gender and Development (GAD) | Gender sensitivity, representation, and inclusive language. |
| Innovation and Technology Support Office (ITSO) | Source use, citations, ownership, confidentiality, and teacher/student rights. |

Coordinator requires a ready curriculum for the confirmed program. It uses
SLM-scoped embeddings to select bounded, exact evidence passages. ITSO requires
public-reference search and retrieved source passages for its source checks;
queries use public citation details or lesson/topic names rather than private
body passages. Missing evidence and retrieval limits remain visible in results.

A completed specialist run fills its domain in the monitoring matrix. The
weighted composite appears after all four domains complete: SME 35%, Coordinator
30%, GAD 20%, and ITSO 15%. Coordinator's curriculum-alignment supplement is
excluded from the official average, composite, and institutional scorecard PDF.

## Evaluation workflow

1. Upload an owned SLM PDF and wait for document processing to finish.
2. Open a permitted specialist workspace, confirm the program, and select any
   required institutional reference.
3. Start the evaluation and follow its server-reported progress.
4. Inspect the saved scores, reasoning, quotations, source checks, and limitations.
5. Record review feedback or export the institutional form. Re-evaluation creates
   another run without replacing its history.

Standalone Syllabus check and Curriculum check remain separate from specialist
scoring. See the [evaluation guide](docs/evaluation.md) for prerequisites and how
to interpret each specialist's output.

## Technology and structure

| Area | Technology |
| --- | --- |
| Faculty and Admin portals | React 18, TypeScript, Vite, and shared UI components. |
| Backend | Python 3.12 and a single-process FastAPI modular monolith. |
| Specialist harness | Independent Python package under `libs/evaluation-harness`. |
| Relational data | PostgreSQL with SQLAlchemy and Alembic migrations. |
| Vector retrieval | Configured local/private ChromaDB or explicitly authorized Chroma Cloud. |
| Document processing | PDF extraction and Tesseract OCR. |
| Workspace tools | pnpm 9.12.0, uv, and optional Caddy/Docker services. |

The server owns authorization, source preparation, durable jobs, persistence,
and deterministic synthesis. The harness owns specialist prompts, evidence
interpretation, scoring, validation, and public-reference tools. See
[architecture](ARCHITECTURE.md) for the component boundaries and data flow.

## Quick start

Use Python 3.12, Node.js 20, pnpm 9.12.0, and uv. Scanned PDFs also require
Tesseract with `eng` and `fil` language data. Caddy provides the optional unified
local origin; Docker is optional.

From the repository root, create `.env` only if it does not already exist:

```sh
test -e .env || cp .env.example .env
uv sync --project apps/server
pnpm install
```

Configure the database, approved model endpoint, email delivery, and document and
vector storage in `.env`. ITSO requires authorized public-reference access with
`ITSO_VERIFICATION_ENABLED=true`. Use a separate migration-owner database
connection when applying schema upgrades, then restore the runtime connection.
The [setup guide](docs/setup.md) includes the configuration details and
PowerShell equivalent.

Start the application:

```sh
pnpm dev:all
```

Open <http://localhost:3000> with Caddy, or <http://localhost:5173> through the
Faculty Vite proxy when Caddy is unavailable. FastAPI's interactive documentation
is at <http://localhost:8000/docs> while the backend is running.

## Common commands

| Task | Command |
| --- | --- |
| Start both portals, backend, and optional proxy | `pnpm dev:all` |
| Start both frontend servers | `pnpm dev` |
| Start backend | `pnpm server:dev` |
| Start Caddy proxy | `pnpm dev:proxy` |
| Apply database migrations with the owner connection | `pnpm server:migrate` |
| Run frontend/library tests | `pnpm test` |
| Run backend and harness tests | `pnpm server:test` |
| Run harness tests | `pnpm harness:test` |
| Lint frontend workspace / backend | `pnpm lint` / `pnpm server:lint` |
| Typecheck / build frontend workspace | `pnpm typecheck` / `pnpm build` |

Backend commands use the root scripts or run from `apps/` so `server.*` imports
resolve correctly. Compose configuration and deployment constraints are covered
in [operations](docs/operations.md).

## Repository guide

| Path | Contents |
| --- | --- |
| [`apps/faculty/`](apps/faculty/) | Faculty portal and its self-contained features. |
| [`apps/admin/`](apps/admin/) | Administrative workspaces and monitoring. |
| [`apps/server/`](apps/server/) | FastAPI application, domain modules, migrations, and backend tests. |
| [`libs/`](libs/) | Shared frontend packages and the evaluation harness. |
| [`colab/`](colab/) | Training and adapter-conversion notebook templates. |
| [`training/`](training/) | Standalone training, serving, and adapter-validation tools. |
| [`infra/`](infra/) | Proxy, container, and PostgreSQL operating resources. |
| [`assets/branding/`](assets/branding/) | README branding for light and dark backgrounds. |
| [`docs/`](docs/) | Evaluation, setup, operations, training, and component guides. |

## Data and deployment

Access is authenticated and ownership-scoped. Institutional documents, vectors,
and inference remain within explicitly authorized systems. Cloud storage does
not authorize external inference. Public-reference checks exclude private body
passages and personal data from queries.

PostgreSQL records, document binaries, and vector data are separate assets and
need separate recovery procedures. The deployment target is institution-controlled
infrastructure. Included Compose files require deployment-specific configuration
and verification; see [operations and deployment](docs/operations.md).

## Documentation

- [Thesis showcase](https://lspu-equiped.github.io/EquipED/) · [Site maintenance](site/README.md)

- [Product overview](PRODUCT.md) and [requirements](PRD.md)
- [Architecture](ARCHITECTURE.md) and [design system](DESIGN.md)
- [Evaluation workflow](docs/evaluation.md)
- [Setup](docs/setup.md) and [operations](docs/operations.md)
- [Training workflow](docs/training.md) and [harness API](libs/evaluation-harness/README.md)
- [Complete documentation index](docs/README.md)
