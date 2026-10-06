# Institutional specialist export templates

These static PDFs are byte-for-byte copies of the official forms under
`apps/server/data/rubrics/source/`. Vite bundles them as local assets.

| Asset | Source form |
| --- | --- |
| sme.pdf | LSPU-CID-SF-002 |
| coordinator.pdf | LSPU-CID-SF-003 |
| gad.pdf | LSPU-CID-SF-004 |
| itso.pdf | LSPU-CID-SF-005 |

`layouts.json` records source dimensions, printed wording, score-cell rectangles,
total cells, text baselines, canonical legacy codes/titles and SHA-256 hashes. Coordinates are PDF points from
the top left. The source forms are Rev. 0, 23 May 2022; their revision is distinct
from the saved evaluation's rubric revision.

Export preserves the source PDF as vector content and fills only its existing
fields on one page. Match saved descriptions to printed wording; legacy results
without descriptions require both a canonical code and title. Never map by row
order or reuse a code when a saved description has changed. Complete sections
receive totals; only a complete form match receives an average and its rating.
Recorded scores flagged as ungrounded remain advisory scores, with a brief
review notice in the original comments area. Unavailable/revised criteria stay
blank with a comment; failed output does not fill scores. All filled text uses the PDF-standard Times serif face at 12 pt. The evaluation
date is centered on its printed rule. Average and rating baselines stay slightly
above their rules; summaries align with `commentBaselines`, measured from each
source PDF. They fit
within the four existing comment lines. There are no added headers, footers or pages.

The download loads missing metadata through the existing document and session
APIs: faculty name from the authenticated faculty account, course title and
academic year from the selected module, and the college code from its canonical
program mapping. Explicit values take precedence; unsupported/missing fields
stay blank. Program, module title and reviewer are not substitutes for college,
course title and faculty name respectively. The evaluator’s printed name is centered in uppercase on
`signatureNameLine`, using the same 12 pt Times face. An explicit reviewer name
takes precedence; otherwise use the authenticated faculty account that owns the
evaluation. Missing names stay blank. The signature itself remains for manual
signing. Date evaluated uses the saved completion date only for completed
evaluations, never the download date. No external service receives report data.

When replacing a source PDF, update its copy, layout and checksum together,
then render all four filled forms.
