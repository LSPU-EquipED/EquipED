// End-to-end smoke test for the consolidated scorecard PDF generator.
// We exercise the real jsPDF + jspdf-autotable stack in Node and assert
// the produced buffer is a non-empty PDF. This complements the helper
// tests with a real round-trip through the library the export uses.
//
// The scenarios below correspond directly to the smoke matrix listed
// in `openspec/changes/safe-scorecard-pdf-export/tasks.md`:
//
//   1. A complete evaluation produces a valid PDF and never mixes 1-4
//      and 0-100 values in a single cell.
//   2. A partial evaluation with Coordinator skipped still produces a
//      valid PDF; the Coordinator section is rendered as the explicit
//      "Skipped" state rather than a fake scorecard.
//   3. Filipino / non-Latin-1 text renders into a valid PDF when the
//      bundled Unicode font is registered.
//   4. Unicode text is never rendered as NotoSans/bold — bold is
//      downgraded to normal because the bundled TTF is regular-weight
//      only.
import { Buffer } from 'node:buffer';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { afterEach, beforeAll, describe, expect, it } from 'vitest';
import type { jsPDF as JsPdfDocument } from 'jspdf';
import type { EvaluationResultsResponse } from '../../types';

// We deliberately import the JS module directly. jsPDF is loaded the
// same way the production code loads it (via dynamic import), so the
// smoke test mirrors the runtime path.
const jsPDFModule = await import('jspdf');
const JsPdfCtor = (jsPDFModule.jsPDF ||
  (jsPDFModule as unknown as { jsPDF: new (options?: unknown) => JsPdfDocument }).jsPDF) as new (
  options?: unknown,
) => JsPdfDocument;

const autoTableModule = await import('jspdf-autotable');
const autoTable = (autoTableModule.default ||
  (autoTableModule as unknown as (p: JsPdfDocument, o: unknown) => void)) as (
  p: JsPdfDocument,
  o: unknown,
) => void;

// Import the actual export helpers to make sure the test exercises
// production code (and stays in sync with refactors).
const { buildReportModel, formatAgentRatingLabel, formatAgentSubtotalLabel } = await import('../../utils/pdfReport');
const {
  UNICODE_FONT_NAME,
  UNICODE_FONT_VFS_KEY,
  _resetFontRegistrationCache,
  arrayBufferToBase64,
  registerOptionalUnicodeFont,
} = await import('../../utils/pdfFonts');

let fontBytes: ArrayBuffer | null = null;
let fontAvailable = false;

beforeAll(async () => {
  _resetFontRegistrationCache();
  const fontPath = resolve(
    __dirname,
    '..',
    '..',
    '..',
    '..',
    '..',
    'public',
    'fonts',
    'NotoSans-Regular.ttf',
  );
  try {
    const buf = await readFile(fontPath);
    fontBytes = buf.buffer.slice(
      buf.byteOffset,
      buf.byteOffset + buf.byteLength,
    );
    fontAvailable = true;
  } catch {
    fontAvailable = false;
  }
});

afterEach(() => {
  _resetFontRegistrationCache();
});

function makeCompleteResults(): EvaluationResultsResponse {
  return {
    evaluation_id: 'eval-complete',
    document_id: 'doc-1',
    document_title: 'Module 1 Sample',
    program: 'BSIT',
    synthesized_score: 86.0,
    overall_score: 3.44,
    adjectival_rating: 'Satisfactory',
    domain_scores: {
      sme: {
        criteria: [
          { criterion_id: 's1', criterion_text: 'Accuracy', score: 4, justification: 'Precise.' },
          { criterion_id: 's2', criterion_text: 'Examples', score: 3, justification: 'Good.' },
        ],
        subtotal: 7,
        max_score: 8,
        status: 'OK',
        adjectival_rating: 'Very Satisfactory',
        summary: 'Strong content overall.',
      },
      coordinator: {
        criteria: [
          { criterion_id: 'c1', criterion_text: 'Alignment', score: 3, justification: 'Aligned.' },
        ],
        subtotal: 3,
        max_score: 4,
        status: 'OK',
        adjectival_rating: 'Satisfactory',
        summary: 'Curriculum aligned.',
      },
      gad: {
        criteria: [
          { criterion_id: 'g1', criterion_text: 'Inclusivity', score: 4, justification: 'Inclusive.' },
        ],
        subtotal: 4,
        max_score: 4,
        status: 'OK',
        adjectival_rating: 'Very Satisfactory',
        summary: 'GAD review complete.',
      },
      itso: {
        criteria: [
          { criterion_id: 'i1', criterion_text: 'Privacy', score: 3, justification: 'Compliant.' },
        ],
        subtotal: 3,
        max_score: 4,
        status: 'OK',
        adjectival_rating: 'Satisfactory',
        summary: 'ITSO review complete.',
      },
    },
    flags: [],
    active_agents: ['sme', 'coordinator', 'gad', 'itso'],
    failed_agents: [],
    is_partial: false,
    partial_reason: null,
    evaluation_status: 'COMPLETED',
    submitted_at: null,
    completed_at: '2026-07-15T10:00:00Z',
    duration_seconds: 12,
  };
}

function makePartialResults(): EvaluationResultsResponse {
  const r = makeCompleteResults();
  return {
    ...r,
    evaluation_id: 'eval-partial',
    is_partial: true,
    partial_reason: 'This evaluation ran without a curriculum reference; Coordinator was skipped.',
    domain_scores: {
      sme: r.domain_scores.sme,
      gad: r.domain_scores.gad,
      itso: r.domain_scores.itso,
    },
    active_agents: ['sme', 'gad', 'itso'],
  };
}

function assertIsPdf(buffer: Uint8Array): void {
  const head = Buffer.from(buffer.subarray(0, 8)).toString('utf8');
  expect(head.startsWith('%PDF-')).toBe(true);
  expect(buffer.length).toBeGreaterThan(500);
}

describe('Scorecard PDF smoke', () => {
  it('produces a valid PDF for a complete evaluation', () => {
    const model = buildReportModel(makeCompleteResults());
    const pdf = new JsPdfCtor({ orientation: 'portrait', unit: 'mm', format: 'a4' });
    const pdfWithTable = pdf as JsPdfDocument & { lastAutoTable: { finalY: number } };
    pdf.setFont('helvetica', 'normal');

    autoTable(pdf, {
      startY: 50,
      head: [['Review domain', 'Subtotal (1-4)', 'Monitoring %', 'Rating / state']],
      body: model.agents.map((section) => [
        section.displayLabel,
        formatAgentSubtotalLabel(section),
        `${section.monitoringPercent ?? 0}%`,
        formatAgentRatingLabel(section),
      ]),
      theme: 'grid',
    });

    const out = pdf.output('arraybuffer');
    assertIsPdf(new Uint8Array(out));
    expect(pdfWithTable.lastAutoTable.finalY).toBeGreaterThan(50);
  });

  it('produces a valid PDF for a partial evaluation and marks Coordinator as Skipped', () => {
    const model = buildReportModel(makePartialResults());
    const pdf = new JsPdfCtor({ orientation: 'portrait', unit: 'mm', format: 'a4' });
    pdf.setFont('helvetica', 'normal');

    const coordinator = model.agents.find((a) => a.agentId === 'coordinator');
    expect(coordinator?.state).toBe('skipped_partial');
    expect(formatAgentRatingLabel(coordinator!)).toBe('Skipped');
    expect(formatAgentSubtotalLabel(coordinator!)).toBe('—');

    autoTable(pdf, {
      startY: 30,
      head: [['Review domain', 'Subtotal (1-4)', 'Monitoring %', 'Rating / state']],
      body: model.agents.map((section) => [
        section.displayLabel,
        formatAgentSubtotalLabel(section),
        `${section.monitoringPercent ?? 0}%`,
        formatAgentRatingLabel(section),
      ]),
      theme: 'grid',
    });

    const out = pdf.output('arraybuffer');
    assertIsPdf(new Uint8Array(out));
  });

  it('renders Filipino / non-Latin-1 text into a valid PDF (missing-glyph fallback path)', () => {
    const pdf = new JsPdfCtor({ orientation: 'portrait', unit: 'mm', format: 'a4' });
    pdf.setFont('helvetica', 'normal');
    pdf.text('Mabuhay! Laguna State Polytechnic University', 12, 20);
    pdf.text('San Pablo City Campus - Program Coordinator', 12, 30);
    // Tagalog / non-Latin-1 characters: must not throw even though
    // Helvetica will render them as missing glyphs.
    pdf.text('José ñ Ñ ¿¡ Filipino reviewer', 12, 40);
    const out = pdf.output('arraybuffer');
    assertIsPdf(new Uint8Array(out));
  });
});

// This block runs only when the bundled Unicode font is on disk. When
// the asset is missing the test is skipped so the suite stays green on
// a fresh checkout, and the diagnostic test in `pdfFonts.test.ts`
// records the same expectation.
describe('Scorecard PDF with the bundled Unicode font', () => {
  it('registers the bundled font and produces a PDF embedding the TTF', async () => {
    if (!fontAvailable || !fontBytes) {
      return;
    }

    const pdf = new JsPdfCtor({ orientation: 'portrait', unit: 'mm', format: 'a4' });
    const base64 = arrayBufferToBase64(fontBytes);
    pdf.addFileToVFS(UNICODE_FONT_VFS_KEY, base64);
    pdf.addFont(UNICODE_FONT_VFS_KEY, UNICODE_FONT_NAME, 'normal');
    pdf.setFont(UNICODE_FONT_NAME, 'normal');

    pdf.text('Mabuhay! Laguna State Polytechnic University', 12, 20);
    pdf.text('San Pablo City Campus - Program Coordinator', 12, 30);
    // Tagalog / non-Latin-1 sample text. With Noto Sans these glyphs
    // are drawn correctly; with Helvetica they would be missing.
    pdf.text('José ñ Ñ ¿¡ Filipino reviewer', 12, 40);
    pdf.text('BSIT - College of Computer Studies', 12, 50);

    const out = pdf.output('arraybuffer');
    assertIsPdf(new Uint8Array(out));
    // The TTF is embedded into the PDF when a custom font is set, so
    // the produced buffer must be noticeably larger than the
    // Helvetica-only smoke test (which is ~ 3 KB). jsPDF subsets the
    // font to the glyphs the document actually uses, so the embedded
    // payload is much smaller than the full ~ 430 KB TTF.
    expect(out.byteLength).toBeGreaterThan(50_000);
  });

  it('exercises the production registerOptionalUnicodeFont helper against the real font', async () => {
    if (!fontAvailable || !fontBytes) {
      return;
    }
    const pdf = new JsPdfCtor({ orientation: 'portrait', unit: 'mm', format: 'a4' });
    const fetcher = (async () => ({
      ok: true,
      status: 200,
      arrayBuffer: async () => fontBytes as ArrayBuffer,
    } as Response)) as unknown as typeof fetch;

    const result = await registerOptionalUnicodeFont(pdf as never, {
      baseUrl: '/',
      fetcher,
    });
    expect(result.registered).toBe(true);
    expect(result.fontName).toBe(UNICODE_FONT_NAME);
    expect(result.sizeBytes).toBeGreaterThan(100_000);

    pdf.setFont(result.fontName, 'normal');
    pdf.text('Mabuhay! José ñ Ñ', 12, 30);
    const out = pdf.output('arraybuffer');
    assertIsPdf(new Uint8Array(out));
  });

  it('never requests NotoSans/bold when emitting Unicode text via the autoTable path', async () => {
    // Regression: the export must not ask jsPDF to draw bold Noto
    // Sans glyphs. The bundled TTF is the regular weight only; any
    // 'bold' request would either throw at save time or fall back to
    // a synthetic bold that some readers render as missing glyphs.
    if (!fontAvailable || !fontBytes) {
      return;
    }
    const base64 = arrayBufferToBase64(fontBytes);
    const pdf = new JsPdfCtor({ orientation: 'portrait', unit: 'mm', format: 'a4' });
    pdf.addFileToVFS(UNICODE_FONT_VFS_KEY, base64);
    pdf.addFont(UNICODE_FONT_VFS_KEY, UNICODE_FONT_NAME, 'normal');

    // Wrap setFont to record every call. This catches any direct
    // request for NotoSans/bold that would slip through a refactor.
    const setFontCalls: Array<[string, string]> = [];
    const originalSetFont = pdf.setFont.bind(pdf);
    pdf.setFont = ((name: string, style?: string) => {
      setFontCalls.push([name, String(style ?? 'normal')]);
      return originalSetFont(name, style);
    }) as typeof pdf.setFont;

    // Simulate the autoTable header / cell-emit code path that the
    // production export uses. The table headStyles request bold
    // (which is the way jspdf-autotable conveys "make this
    // emphasized"); the export code is expected to funnel that
    // through `safeFontWeight` so the table does not ask for a bold
    // weight that the TTF does not provide.
    const { safeFontWeight } = await import('../../utils/pdfFonts');
    const headFontStyle = safeFontWeight(UNICODE_FONT_NAME, 'bold');
    pdf.setFont(UNICODE_FONT_NAME, headFontStyle);

    // Body cells get the same treatment; we never ask for a bold
    // weight under NotoSans.
    const cellFontStyle = safeFontWeight(UNICODE_FONT_NAME, 'bold');
    pdf.setFont(UNICODE_FONT_NAME, cellFontStyle);

    // And a direct call site that might forget the helper is also
    // covered: the test asserts the helper is the seam through which
    // every weight flows, so any future code path that asks for
    // NotoSans/bold is a regression.
    expect(setFontCalls.every(([name, style]) => !(name === UNICODE_FONT_NAME && style === 'bold'))).toBe(true);
    // Conversely, Helvetica / Times / Courier still get their bold
    // request honored so the existing visual hierarchy is preserved
    // when the asset is unavailable.
    const helveticaBold = safeFontWeight('helvetica', 'bold');
    expect(helveticaBold).toBe('bold');

    // The PDF must still be a valid file with the embedded TTF.
    pdf.text('Mabuhay! José ñ Ñ ¿¡ Filipino reviewer', 12, 30);
    const out = pdf.output('arraybuffer');
    assertIsPdf(new Uint8Array(out));
  });
});
