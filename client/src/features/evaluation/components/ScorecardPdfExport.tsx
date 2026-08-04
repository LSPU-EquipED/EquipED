import { useState } from 'react';
import { Download } from 'lucide-react';
import type { jsPDF as JsPdfDocument } from 'jspdf';
import type { EvaluationResultsResponse } from '../types';
import {
  buildReportModel,
  formatAgentMonitoringLabel,
  formatAgentRatingLabel,
  formatAgentSubtotalLabel,
  formatHeaderField,
  type ReportAgentSection,
  type ReportModel,
} from '../utils/pdfReport';
import {
  PDF_PAGE_BOTTOM_MM,
  formatScore,
} from '../utils/scoreHelpers';
import {
  registerOptionalUnicodeFont,
  safeFontWeight,
  UNICODE_FONT_NAME,
  type FontWeight,
} from '../utils/pdfFonts';

type ScorecardPdfExportProps = {
  results: EvaluationResultsResponse;
};

type AutoTablePlugin = (pdf: JsPdfDocument, options: Record<string, unknown>) => void;

async function loadAutoTable(): Promise<AutoTablePlugin> {
  const mod = await import('jspdf-autotable');
  return (mod.default || (mod as unknown as AutoTablePlugin)) as AutoTablePlugin;
}

async function loadJsPdf(): Promise<new (options?: unknown) => JsPdfDocument> {
  const mod = await import('jspdf');
  return (mod.jsPDF || (mod as unknown as { jsPDF: new (options?: unknown) => JsPdfDocument }).jsPDF) as new (
    options?: unknown,
  ) => JsPdfDocument;
}

async function loadLogoDataUrl(): Promise<string | null> {
  try {
    const base = (import.meta.env?.BASE_URL as string | undefined) ?? '/';
    const response = await fetch(`${base.replace(/\/?$/, '/')}lspu-logo.png`);
    if (!response.ok) return null;
    const blob = await response.blob();
    return await new Promise<string | null>((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : null);
      reader.onerror = () => resolve(null);
      reader.readAsDataURL(blob);
    });
  } catch {
    return null;
  }
}

function formatTimestamp(value?: string | null): string {
  if (!value) return 'Not available';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en-PH', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

// The single seam through which the export talks to jsPDF's font
// registry. The bundled Unicode font is registered as 'normal' only;
// calling `setFont` with a weight that wasn't registered either
// throws or falls back to a synthetic bold that some PDF readers
// render as missing glyphs. `safeFontWeight` downgrades the request
// when the active font is NotoSans, and the visual hierarchy is
// preserved through other channels (size, color, capitalization,
// fillColor on table headers).
function applyFont(pdf: JsPdfDocument, fontName: string, weight: FontWeight = 'normal'): string {
  pdf.setFont(fontName, safeFontWeight(fontName, weight));
  return fontName;
}

// `setFontSize` + bold-or-not in one call. Centralising it here is
// what makes the "no bold under NotoSans" invariant impossible to
// accidentally break from a new caller.
function setTextStyle(
  pdf: JsPdfDocument,
  fontName: string,
  size: number,
  weight: FontWeight = 'normal',
): void {
  pdf.setFontSize(size);
  applyFont(pdf, fontName, weight);
}

// AutoTable `fontStyle` is what makes cell text bold. The same
// "downgrade under NotoSans" rule applies: we return 'bold' for
// built-in Helvetica and 'normal' for NotoSans. The table header
// still gets visual emphasis via `fillColor` and `textColor`.
function safeTableFontStyle(fontName: string): 'normal' | 'bold' {
  return safeFontWeight(fontName, 'bold');
}

function drawPageFooter(
  pdf: JsPdfDocument,
  activeFont: string,
  margin: number,
  pageWidth: number,
): void {
  const pageCount = pdf.getNumberOfPages();
  for (let page = 1; page <= pageCount; page += 1) {
    pdf.setPage(page);
    pdf.setDrawColor(226, 232, 240);
    pdf.line(margin, 283, pageWidth - margin, 283);
    setTextStyle(pdf, activeFont, 7.5, 'normal');
    pdf.setTextColor(71, 85, 105);
    pdf.text('EquipED - LSPU SCC', margin, 289);
    pdf.text(`Page ${page} of ${pageCount}`, pageWidth / 2, 289, { align: 'center' });
    pdf.text('Human review authoritative', pageWidth - margin, 289, { align: 'right' });
  }
}

function ensureRoom(pdf: JsPdfDocument, y: number, needed: number, margin: number): number {
  if (y + needed > PDF_PAGE_BOTTOM_MM) {
    pdf.addPage('a4', 'portrait');
    return margin;
  }
  return y;
}

function drawAgentSection(
  pdf: JsPdfDocument,
  autoTable: AutoTablePlugin,
  section: ReportAgentSection,
  activeFont: string,
  startY: number,
  margin: number,
  contentWidth: number,
): number {
  let y = startY;
  const estimated = section.criteria.length > 0 ? 16 + section.criteria.length * 9 : 18;
  y = ensureRoom(pdf, y, estimated, margin);

  // Per-agent section title. Visual emphasis comes from a larger
  // size and a colored label rather than from a bold weight.
  pdf.setFontSize(12);
  applyFont(pdf, activeFont, 'bold');
  if (section.state === 'available') {
    pdf.setTextColor(27, 59, 135);
  } else if (section.state === 'skipped_partial') {
    pdf.setTextColor(146, 64, 14);
  } else {
    pdf.setTextColor(185, 28, 28);
  }
  pdf.text(section.displayLabel.toUpperCase(), margin, y);

  setTextStyle(pdf, activeFont, 8.5, 'normal');
  pdf.setTextColor(71, 85, 105);
  const subtitle =
    section.state === 'available'
      ? `Subtotal ${formatAgentSubtotalLabel(section)}  -  Adjectival ${formatAgentRatingLabel(section)}  -  Monitoring ${formatAgentMonitoringLabel(section)}`
      : section.state === 'skipped_partial'
        ? 'Coordinator review was skipped (partial evaluation).'
        : section.state === 'failed'
          ? 'Agent result unavailable.'
          : 'No result recorded.';
  pdf.text(subtitle, margin, y + 5);
  y += 11;

  if (section.state !== 'available') {
    setTextStyle(pdf, activeFont, 8.5, 'normal');
    pdf.setTextColor(60, 60, 60);
    const reasonLines = pdf.splitTextToSize(section.stateReason || 'Not available.', contentWidth);
    pdf.text(reasonLines, margin, y);
    return y + reasonLines.length * 3.8 + 4;
  }

  if (section.criteria.length === 0) {
    setTextStyle(pdf, activeFont, 8.5, 'normal');
    pdf.setTextColor(80, 80, 80);
    pdf.text('No criteria were recorded for this agent.', margin, y);
    return y + 8;
  }

  autoTable(pdf, {
    startY: y,
    margin: { top: margin, right: margin, bottom: 15, left: margin },
    head: [['#', 'Criterion (1-4 scale)', 'Score', 'Tier', 'Notes']],
    body: section.criteria.map((c) => [
      String(c.index),
      c.text,
      c.score.toFixed(2),
      c.tierLabel,
      c.note || '—',
    ]),
    theme: 'grid',
    styles: {
      font: activeFont,
      fontSize: 7,
      cellPadding: 1.6,
      lineColor: [148, 163, 184],
      lineWidth: 0.2,
      textColor: [30, 41, 59],
      valign: 'top',
    },
    // Header emphasis is conveyed via the dark fillColor + white
    // textColor + slightly larger fontSize. Bold is added only when
    // the active font supports it (i.e. not NotoSans).
    headStyles: {
      fillColor: [27, 59, 135],
      textColor: [255, 255, 255],
      fontStyle: safeTableFontStyle(activeFont),
      fontSize: 7.5,
    },
    columnStyles: {
      0: { cellWidth: 8, halign: 'center' },
      1: { cellWidth: 60 },
      2: { cellWidth: 16, halign: 'center' },
      3: { cellWidth: 25 },
      4: { cellWidth: 'auto' },
    },
    didParseCell: (data: { section?: string; column?: { index: number }; cell: { raw?: unknown; styles: Record<string, unknown> } }) => {
      if (data.section !== 'body' || data.column?.index !== 3) return;
      const text = String(data.cell.raw ?? '');
      if (text === 'Needs attention') {
        data.cell.styles.textColor = [185, 28, 28];
        data.cell.styles.fontStyle = safeTableFontStyle(activeFont);
      } else if (text === 'Strong') {
        data.cell.styles.textColor = [59, 150, 62];
      }
    },
  });
  const pdfWithTable = pdf as JsPdfDocument & { lastAutoTable: { finalY: number } };
  return pdfWithTable.lastAutoTable.finalY + 8;
}

function drawFlagSection(
  pdf: JsPdfDocument,
  autoTable: AutoTablePlugin,
  model: ReportModel,
  activeFont: string,
  startY: number,
  margin: number,
): number {
  let y = startY;
  y = ensureRoom(pdf, y, 20, margin);

  // Section heading. The 'bold' weight is downgraded to 'normal'
  // under NotoSans, but the red color and 11pt size still stand
  // out against the surrounding body copy.
  pdf.setFontSize(11);
  applyFont(pdf, activeFont, 'bold');
  pdf.setTextColor(185, 28, 28);
  pdf.text('Items requiring human attention', margin, y);

  autoTable(pdf, {
    startY: y + 3,
    margin: { top: margin, right: margin, bottom: 15, left: margin },
    head: [['Agent', 'Score (1-4)', 'Criterion', 'Reason']],
    body: model.flags.map((flag) => [
      flag.agentLabel,
      flag.score == null ? '—' : `${formatScore(flag.score)}/4`,
      flag.criterionText,
      flag.reason || '—',
    ]),
    theme: 'grid',
    styles: {
      font: activeFont,
      fontSize: 7,
      cellPadding: 1.6,
      lineColor: [148, 163, 184],
      lineWidth: 0.2,
      textColor: [30, 41, 59],
      valign: 'top',
    },
    headStyles: {
      fillColor: [185, 28, 28],
      textColor: [255, 255, 255],
      fontStyle: safeTableFontStyle(activeFont),
      fontSize: 7.5,
    },
    columnStyles: {
      0: { cellWidth: 42 },
      1: { cellWidth: 18, halign: 'center' },
      2: { cellWidth: 50 },
      3: { cellWidth: 'auto' },
    },
  });
  const pdfWithTable = pdf as JsPdfDocument & { lastAutoTable: { finalY: number } };
  return pdfWithTable.lastAutoTable.finalY + 8;
}

async function exportScorecardPdf(results: EvaluationResultsResponse): Promise<void> {
  const JsPdfCtor = await loadJsPdf();
  const autoTable = await loadAutoTable();

  const model = buildReportModel(results);
  const pdf = new JsPdfCtor({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  const pdfWithTable = pdf as JsPdfDocument & { lastAutoTable: { finalY: number } };
  const pageWidth = pdf.internal.pageSize.getWidth();
  const margin = 12;
  const contentWidth = pageWidth - margin * 2;

  const font = await registerOptionalUnicodeFont(pdf);
  const activeFont = font.registered ? font.fontName : 'helvetica';
  applyFont(pdf, activeFont, 'normal');

  const logoDataUrl = await loadLogoDataUrl();
  pdf.setTextColor(30, 41, 59);

  // Header block ---------------------------------------------------------
  // The University name gets the only 'bold' weight we still use for
  // emphasis. Under NotoSans it is rendered at the regular weight,
  // but the size + dark color keeps the visual hierarchy.
  let y = 14;
  if (logoDataUrl) {
    try {
      pdf.addImage(logoDataUrl, 'PNG', margin, y, 18, 18);
    } catch {
      // Text-only fallback is intentional.
    }
    setTextStyle(pdf, activeFont, 9, 'normal');
    pdf.text('Republic of the Philippines', pageWidth / 2, y + 5, { align: 'center' });
    pdf.setFontSize(11);
    applyFont(pdf, activeFont, 'bold');
    pdf.text('Laguna State Polytechnic University', pageWidth / 2, y + 11, { align: 'center' });
    setTextStyle(pdf, activeFont, 9, 'normal');
    pdf.text('EquipED evaluation report', pageWidth / 2, y + 17, { align: 'center' });
  } else {
    pdf.setFontSize(12);
    applyFont(pdf, activeFont, 'bold');
    pdf.text('EquipED Evaluation Report', pageWidth / 2, y + 6, { align: 'center' });
    setTextStyle(pdf, activeFont, 9, 'normal');
    pdf.text('Laguna State Polytechnic University - Evaluation Report', pageWidth / 2, y + 12, { align: 'center' });
  }
  y += 26;

  pdf.setFontSize(14);
  applyFont(pdf, activeFont, 'bold');
  pdf.setTextColor(27, 59, 135);
  pdf.text('Evaluation Scorecard'.toUpperCase(), pageWidth / 2, y, { align: 'center' });
  setTextStyle(pdf, activeFont, 9.5, 'normal');
  pdf.setTextColor(71, 85, 105);
  pdf.text('SLM multi-agent evaluation summary', pageWidth / 2, y + 5, { align: 'center' });
  y += 12;

  pdf.setFontSize(10);
  applyFont(pdf, activeFont, 'bold');
  if (model.header.isPartial) {
    pdf.setTextColor(146, 64, 14);
    pdf.text('PARTIAL EVALUATION - Advisory only', pageWidth / 2, y, { align: 'center' });
  } else {
    pdf.setTextColor(27, 59, 135);
    pdf.text('Advisory only - Human review authoritative', pageWidth / 2, y, { align: 'center' });
  }
  pdf.setTextColor(30, 41, 59);
  y += 8;

  // Identity & state table ----------------------------------------------
  autoTable(pdf, {
    startY: y,
    margin: { right: margin, left: margin },
    body: [
      ['Document', formatHeaderField(model.header.documentTitle, 'Not available')],
      ['Evaluation ID', model.header.evaluationId],
      ['Program', formatHeaderField(model.header.program, 'Not specified')],
      ['Evaluation status', model.header.evaluationStatus],
      [
        'Result state',
        model.header.isPartial
          ? model.header.partialReason
            ? 'Partial evaluation'
            : 'Partial evaluation (no curriculum reference)'
          : 'Complete',
      ],
      ['Completed', formatTimestamp(model.header.completedAt)],
    ],
    theme: 'grid',
    styles: {
      font: activeFont,
      fontSize: 8,
      cellPadding: 2,
      lineColor: [203, 213, 225],
      lineWidth: 0.2,
      textColor: [30, 41, 59],
    },
    columnStyles: {
      // Left-column label gets a slate fillColor to act as a visual
      // anchor; under NotoSans the label is rendered in regular
      // weight but the fillColor + uppercase letterforms still
      // distinguish it.
      0: {
        cellWidth: 36,
        fontStyle: safeTableFontStyle(activeFont),
        fillColor: [248, 250, 252],
        textColor: [27, 59, 135],
      },
      1: { cellWidth: 'auto' },
    },
  });

  y = pdfWithTable.lastAutoTable.finalY + 6;

  if (model.header.isPartial && model.header.partialReason) {
    pdf.setFontSize(10);
    applyFont(pdf, activeFont, 'bold');
    pdf.setTextColor(146, 64, 14);
    pdf.text('Partial evaluation notice', margin, y);
    setTextStyle(pdf, activeFont, 9, 'normal');
    pdf.setTextColor(30, 41, 59);
    const partialLines = pdf.splitTextToSize(model.header.partialReason, contentWidth);
    pdf.text(partialLines, margin, y + 5);
    y += 8 + partialLines.length * 3.5;
  }

  // Overall score banner ------------------------------------------------
  const bannerHeight = 22;
  y = ensureRoom(pdf, y, bannerHeight, margin);
  pdf.setFillColor(239, 246, 255);
  pdf.setDrawColor(27, 59, 135);
  pdf.roundedRect(margin, y, contentWidth, bannerHeight, 1, 1, 'FD');
  if (model.header.hasOverall && model.header.overallScore != null) {
    pdf.setFontSize(11);
    applyFont(pdf, activeFont, 'bold');
    pdf.setTextColor(27, 59, 135);
    pdf.text(
      `Overall (1-4 scale): ${formatScore(model.header.overallScore)} / 4`,
      margin + 4,
      y + 7,
    );
    setTextStyle(pdf, activeFont, 9.5, 'normal');
    pdf.setTextColor(30, 41, 59);
    pdf.text(`Adjectival rating: ${model.header.overallAdjectival}`, margin + 4, y + 14);

    pdf.setFontSize(11);
    applyFont(pdf, activeFont, 'bold');
    pdf.setTextColor(27, 59, 135);
    pdf.text(
      `Monitoring %: ${model.header.monitoringPercent ?? 0}%`,
      pageWidth - margin - 4,
      y + 7,
      { align: 'right' },
    );
    setTextStyle(pdf, activeFont, 8, 'normal');
    pdf.setTextColor(71, 85, 105);
    pdf.text('(0-100 scale, separate)', pageWidth - margin - 4, y + 14, { align: 'right' });
  } else {
    pdf.setFontSize(11);
    applyFont(pdf, activeFont, 'bold');
    pdf.setTextColor(146, 64, 14);
    pdf.text('Overall score: not available', margin + 4, y + 7);
    setTextStyle(pdf, activeFont, 9, 'normal');
    pdf.setTextColor(71, 85, 105);
    pdf.text(
      'No synthesized 1-4 score was produced; this evaluation did not complete successfully.',
      margin + 4,
      y + 14,
    );
  }
  pdf.setTextColor(30, 41, 59);
  y += bannerHeight + 6;

  // Agent summary table -------------------------------------------------
  pdf.setFontSize(11);
  applyFont(pdf, activeFont, 'bold');
  pdf.setTextColor(27, 59, 135);
  y = ensureRoom(pdf, y, 10, margin);
  pdf.text('Agent score summary'.toUpperCase(), margin, y);
  y += 4;

  const summaryRows = model.agents.map((section) => [
    section.displayLabel,
    formatAgentSubtotalLabel(section),
    formatAgentMonitoringLabel(section),
    formatAgentRatingLabel(section),
  ]);

  autoTable(pdf, {
    startY: y,
    margin: { top: margin, right: margin, bottom: 15, left: margin },
    head: [
      [
        { content: 'Review domain', styles: { halign: 'left' } },
        { content: 'Subtotal (1-4)', styles: { halign: 'center' } },
        { content: 'Monitoring % (0-100)', styles: { halign: 'center' } },
        { content: 'Rating / state', styles: { halign: 'left' } },
      ],
    ],
    body: summaryRows,
    theme: 'grid',
    styles: {
      font: activeFont,
      fontSize: 7.5,
      cellPadding: 2,
      lineColor: [148, 163, 184],
      lineWidth: 0.2,
      textColor: [30, 41, 59],
      valign: 'middle',
    },
    headStyles: {
      fillColor: [27, 59, 135],
      textColor: [255, 255, 255],
      fontStyle: safeTableFontStyle(activeFont),
      fontSize: 8,
    },
    columnStyles: {
      0: { cellWidth: 70 },
      1: { cellWidth: 35, halign: 'center' },
      2: { cellWidth: 30, halign: 'center' },
      3: { cellWidth: 'auto' },
    },
    didParseCell: (data: { section?: string; cell: { raw?: unknown; styles: Record<string, unknown> } }) => {
      if (data.section !== 'body') return;
      const label = String(data.cell.raw ?? '');
      if (label === 'Skipped' || label === 'Unavailable' || label === 'Unavailable (failed)') {
        data.cell.styles.textColor = [146, 64, 14];
        data.cell.styles.fontStyle = safeTableFontStyle(activeFont);
      }
    },
  });

  y = pdfWithTable.lastAutoTable.finalY + 8;

  // Per-agent sections --------------------------------------------------
  for (const section of model.agents) {
    y = drawAgentSection(pdf, autoTable, section, activeFont, y, margin, contentWidth);
  }

  // Flag table ----------------------------------------------------------
  if (model.flags.length > 0) {
    drawFlagSection(pdf, autoTable, model, activeFont, y, margin);
  }

  drawPageFooter(pdf, activeFont, margin, pageWidth);

  pdf.save(`EquipED-scorecard-${model.header.evaluationId}.pdf`);
}

export function ScorecardPdfExport({ results }: ScorecardPdfExportProps) {
  const [isExporting, setIsExporting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleExport = async () => {
    setIsExporting(true);
    setErrorMessage(null);
    try {
      await exportScorecardPdf(results);
    } catch (error) {
      console.error('Unable to create the evaluation scorecard PDF.', error);
      setErrorMessage('PDF export failed. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="inline-flex flex-col items-start gap-1">
      <button
        type="button"
        className="inline-flex h-9 items-center justify-center rounded-sm bg-[#1b3b87] px-4 text-xs font-semibold uppercase tracking-wide text-white transition-colors hover:bg-[#1b3b87]/90 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] disabled:cursor-wait disabled:opacity-70"
        onClick={handleExport}
        disabled={isExporting}
      >
        <Download className="mr-1.5 size-4" aria-hidden="true" />
        {isExporting ? 'Creating PDF...' : 'Export Scorecard PDF'}
      </button>
      {errorMessage && (
        <span className="text-xs font-medium text-[#b91c1c]" role="alert">
          {errorMessage}
        </span>
      )}
    </div>
  );
}

// Re-export the active font constant so consumers and tests can detect
// when the Unicode path is in use without re-importing from `pdfFonts`.
export { UNICODE_FONT_NAME };
