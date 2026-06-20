# Product

## Register

product

## Users
* **LSPU SCC Faculty Members**: Instructors submitting Self-Paced Learning Materials (SLMs) for initial automated evaluation, checking flagged text segments, and reviewing criteria scores to guide syllabus/module alignment revisions.
* **CID (Curriculum Instruction Development) Staff & Admin**: Institutional Quality Assurance reviewers who manage system-wide prompts, monitor evaluations across academic programs (BSIT, BSCS, BSIS), validate agent scorecards, and provide authoritative human decisions.

## Product Purpose
To automate the initial quality-assurance review layer of Self-Paced Learning Modules (SLMs) against institutional rubrics across four independent domains (SME content accuracy, Coordinator curriculum alignment, GAD gender sensitivity, and ITSO IP compliance). The system serves as an advisory co-pilot that aggregates evaluation scores and compliance flags under the authoritative review of human CID experts.

## Brand Personality
* **Institutional**: Academic, formal, professional, and highly structured, reflecting official Laguna State Polytechnic University guidelines.
* **Authoritative & Trustworthy**: Clear, precise, and transparent about data residency, grounding sources, and evaluation limits.
* **Academic-Tech**: A clean, balanced synthesis of educational administration standards and modern natural language processing workspace features.

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
