# Institutional approval sheet

`approval-sheet.pdf` is a byte-for-byte copy of the supplied
`LSPU-CID-SF-006-APPROVAL-SHEET-3.pdf` (Rev. 0, 23 May 2022).
SHA-256: `ff5398cee13899e0593782d42a0c86e6173837532923bcc7ac4f8d0186428ed9`.

The export preserves its single vector page, printed labels, institutional header
and footer. `approvalSheetPdf.ts` records measured table bounds and reviewer
rules in points from the top left. Filled text uses 12 pt PDF-standard Times.
Names on reviewer rules are uppercase and centered; signatures stay blank.
Table values can wrap to two lines. Values that cannot fit produce an export
error rather than a silently shortened name or an extra page.

Saved course title and academic year come from the admin-only synthesis detail
response. Completed specialist evaluator names come from that same
record, never from the exporting administrator. Author/s stays blank for manual
completion even when author attribution is recorded. College uses the canonical
program mapping; campus is Santa Cruz. Unrecorded names and metadata remain
blank. Institutional printed names supplied by the user live in
`approvalSheetSignatories.ts`: CID Chairperson, CID Director, VP for Academic
Affairs, and the Dean/Associate Dean for CCS only. These names are uppercase,
centered and complete at 12 pt; they do not represent signatures or approval.
Semester and human approval dates remain blank. No scores, flags,
summaries, record identifiers, extra text, or attachments are added to this form.

When replacing the institutional source, update the asset, measured layout and
checksum together, then render and inspect the complete filled page.
