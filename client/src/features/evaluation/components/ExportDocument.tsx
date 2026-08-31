import { useState } from 'react';
import { DownloadSimple } from '@phosphor-icons/react';
import type { jsPDF as JsPdfDocument } from 'jspdf';
import { cn } from '@/shared/components/utils';
import type { ClientDocument } from '@/shared/types/documents';
import type { CriterionScoreItem, EvaluationResultsResponse } from '../types';
import {
  CANONICAL_MAX_SCORE,
  EXPORT_NARRATIVE_MAX_CHARS,
  PDF_PAGE_BOTTOM_MM,
  adjectivalRating,
  agentDisplayLabel,
  boundNarrative,
  cleanJustification,
  formatScore,
  monitoringPercentage,
} from '../utils/scoreHelpers';
import { registerOptionalUnicodeFont, safeFontWeight, type FontWeight } from '../utils/pdfFonts';

export type ExportAgentId = 'coordinator' | 'sme' | 'gad' | 'itso';

// Minimal domain block used by the per-agent export. The page that owns
// the export builds this block from the full evaluation result and the
// owning document metadata; the export must not invent values that
// weren't provided.
export type ExportDomainData = {
  agentId: ExportAgentId | string;
  documentTitle?: string;
  program?: string | null;
  courseTitle?: string | null;
  courseCode?: string | null;
  academicYear?: string | null;
  semester?: string | null;
  reviewer?: string | null;
  evaluationId?: string;
  isPartial?: boolean;
  partialReason?: string | null;
  evaluationStatus?: string;
  criteria: ReadonlyArray<CriterionScoreItem>;
  subtotal: number;
  max_score: number;
  status: string;
  adjectival_rating?: string;
  summary?: string;
  version?: number | null;
  form_snapshot_id?: string | null;
  legacy_notice?: string | null;
  // Carries the full results payload so the export can show the
  // monitoring % and overall adjectival rating from the same source the
  // scorecard uses.
  results?: EvaluationResultsResponse;
  document?: ClientDocument | null;
};

type ExportDocumentProps = {
  readonly domainData?: ExportDomainData;
  readonly agentId?: ExportAgentId;
};

const AGENT_CONFIGS: Record<string, { code: string; sectionTitle: string; unitName: string }> = {
  coordinator: {
    code: 'LSPU-CID-SF-004',
    sectionTitle: 'A. CURRICULUM ALIGNMENT AND ASSESSMENT',
    unitName: 'PROGRAM COORDINATOR',
  },
  sme: {
    code: 'LSPU-CID-SF-004',
    sectionTitle: 'A. CONTENT ACCURACY AND INSTRUCTIONAL ORGANIZATION',
    unitName: 'SUBJECT MATTER EXPERT',
  },
  gad: {
    code: 'LSPU-CID-SF-004',
    sectionTitle: 'A. INCLUSIVITY AND GENDER SENSITIVITY',
    unitName: 'GENDER AND DEVELOPMENT UNIT',
  },
  itso: {
    code: 'LSPU-CID-SF-004',
    sectionTitle: 'A. INNOVATION, INTELLECTUAL PROPERTY, AND DATA PRIVACY',
    unitName: 'INNOVATION AND TECHNOLOGY SUPPORT OFFICE',
  },
};

type AutoTablePlugin = (pdf: JsPdfDocument, options: Record<string, unknown>) => void;

async function loadAutoTable(): Promise<AutoTablePlugin> {
  const mod = await import('jspdf-autotable');
  return (mod.default || (mod as unknown as AutoTablePlugin)) as AutoTablePlugin;
}

async function loadJsPdf(): Promise<new (options?: unknown) => JsPdfDocument> {
  const mod = await import('jspdf');
  return (mod.jsPDF ||
    (mod as unknown as { jsPDF: new (options?: unknown) => JsPdfDocument }).jsPDF) as new (
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

function applyFont(pdf: JsPdfDocument, fontName: string, weight: FontWeight = 'normal'): void {
  // The bundled Unicode TTF (Noto Sans Regular) is registered with
  // the 'normal' weight only. Calling `setFont` with 'bold' under
  // NotoSans either throws at save time or produces broken glyphs
  // in some PDF readers. `safeFontWeight` downgrades the request
  // when the active font is NotoSans; visual hierarchy in the
  // per-agent export is provided by other channels (size, color,
  // uppercase, fillColor on the rubric header).
  pdf.setFont(fontName, safeFontWeight(fontName, weight));
}

function safeTableFontStyle(fontName: string): 'normal' | 'bold' {
  return safeFontWeight(fontName, 'bold');
}

// Prefer the per-criterion `summary` field when present for SME / Coordinator
// agents (the Supervisor may emit a code-computed summary there). Fall back
// to bounded, sanitized criterion justifications.
function buildComments(domainData: ExportDomainData): string {
  if (
    (domainData.agentId === 'sme' || domainData.agentId === 'coordinator') &&
    domainData.summary
  ) {
    return boundNarrative(domainData.summary, EXPORT_NARRATIVE_MAX_CHARS);
  }
  return domainData.criteria
    .map((c) => boundNarrative(c.justification, Math.floor(EXPORT_NARRATIVE_MAX_CHARS / 2)))
    .filter((line) => line.length > 0)
    .join('\n\n');
}

function buildHeaderLines(domainData: ExportDomainData): Array<{ label: string; value: string }> {
  const lines: Array<{ label: string; value: string }> = [];
  const reviewer = (domainData.reviewer || '').trim();
  lines.push({
    label: 'Name of Reviewer:',
    value: reviewer.length > 0 ? reviewer : 'Not available',
  });
  lines.push({
    label: 'College:',
    value: domainData.program ? `${domainData.program}` : 'Not available',
  });
  lines.push({
    label: 'Course Title:',
    value: (domainData.courseTitle || '').trim() || domainData.documentTitle || 'Not available',
  });
  lines.push({
    label: 'Course Code:',
    value: (domainData.courseCode || '').trim() || 'Not available',
  });
  lines.push({
    label: 'Academic Year:',
    value: (domainData.academicYear || '').trim() || 'Not available',
  });
  lines.push({
    label: 'Semester:',
    value: (domainData.semester || '').trim() || 'Not available',
  });
  return lines;
}

function ensureRoom(pdf: JsPdfDocument, y: number, needed: number, margin: number): number {
  if (y + needed > PDF_PAGE_BOTTOM_MM) {
    pdf.addPage('a4', 'portrait');
    return margin;
  }
  return y;
}

async function downloadExport(domainData: ExportDomainData): Promise<void> {
  const JsPdfCtor = await loadJsPdf();
  const autoTable = await loadAutoTable();

  const config = AGENT_CONFIGS[domainData.agentId] || {
    code: 'LSPU-CID-SF-004',
    sectionTitle: 'EVALUATION CRITERIA',
    unitName: domainData.agentId.toString().toUpperCase(),
  };

  const subtotal = Number.isFinite(domainData.subtotal) ? domainData.subtotal : 0;
  const maxScore =
    Number.isFinite(domainData.max_score) && domainData.max_score > 0
      ? domainData.max_score
      : CANONICAL_MAX_SCORE;
  const rating = domainData.adjectival_rating || adjectivalRating(subtotal);
  const monitoring = monitoringPercentage(subtotal, maxScore);

  const pdf = new JsPdfCtor({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  const pdfWithTable = pdf as JsPdfDocument & { lastAutoTable: { finalY: number } };
  const pageWidth = pdf.internal.pageSize.getWidth();
  const margin = 12;
  const contentWidth = pageWidth - margin * 2;

  const font = await registerOptionalUnicodeFont(pdf);
  const activeFont = font.registered ? font.fontName : 'helvetica';
  applyFont(pdf, activeFont, 'normal');
  const logo = await loadLogoDataUrl();
  pdf.setTextColor(17, 24, 39);

  // Header block ---------------------------------------------------------
  // The University name and the form title use a 'bold' weight that
  // is downgraded to 'normal' under NotoSans; size + color carry the
  // visual hierarchy in that case.
  let y = 12;
  if (logo) {
    try {
      pdf.addImage(logo, 'PNG', margin + 2, y, 18, 18);
    } catch {
      // Fall through to text-only header.
    }
    pdf.setFontSize(9);
    applyFont(pdf, activeFont, 'normal');
    pdf.text('Republic of the Philippines', pageWidth / 2, y + 4, { align: 'center' });
    pdf.setFontSize(11);
    applyFont(pdf, activeFont, 'bold');
    pdf.setTextColor(27, 59, 135);
    pdf.text('Laguna State Polytechnic University', pageWidth / 2, y + 10, { align: 'center' });
    pdf.setTextColor(17, 24, 39);
    pdf.setFontSize(9);
    applyFont(pdf, activeFont, 'normal');
    pdf.text('EquipED evaluation report', pageWidth / 2, y + 16, { align: 'center' });
  } else {
    pdf.setFontSize(12);
    applyFont(pdf, activeFont, 'bold');
    pdf.setTextColor(27, 59, 135);
    pdf.text('EquipED Evaluation Report', pageWidth / 2, y + 4, { align: 'center' });
    pdf.setTextColor(17, 24, 39);
    pdf.setFontSize(9);
    applyFont(pdf, activeFont, 'normal');
    pdf.text('Laguna State Polytechnic University - Evaluation Report', pageWidth / 2, y + 10, {
      align: 'center',
    });
  }
  y += 24;

  pdf.setFontSize(13);
  applyFont(pdf, activeFont, 'bold');
  pdf.setTextColor(27, 59, 135);
  pdf.text('CRITERIA FOR EVALUATION OF INSTRUCTIONAL MATERIALS', pageWidth / 2, y, {
    align: 'center',
  });
  pdf.setFontSize(10);
  applyFont(pdf, activeFont, 'normal');
  pdf.setTextColor(17, 24, 39);
  const revisionSuffix =
    domainData.version != null
      ? ` (Revision ${domainData.version})`
      : domainData.legacy_notice || domainData.form_snapshot_id == null
        ? ' (Legacy — form snapshot unavailable)'
        : '';
  pdf.text(`FOR ${config.unitName}${revisionSuffix}`, pageWidth / 2, y + 6, { align: 'center' });
  y += 14;

  // Honest state banner -------------------------------------------------
  if (domainData.isPartial) {
    pdf.setFontSize(10);
    applyFont(pdf, activeFont, 'bold');
    pdf.setTextColor(146, 64, 14);
    pdf.text('PARTIAL EVALUATION - Advisory only', pageWidth / 2, y, { align: 'center' });
    pdf.setTextColor(17, 24, 39);
    y += 5;
    if (domainData.partialReason) {
      pdf.setFontSize(8);
      applyFont(pdf, activeFont, 'normal');
      const lines = pdf.splitTextToSize(domainData.partialReason, contentWidth);
      pdf.text(lines, pageWidth / 2, y, { align: 'center' });
      y += lines.length * 3.5;
    }
    y += 3;
  }

  // Header field table (no hard-coded claims) ---------------------------
  const headerLines = buildHeaderLines(domainData);
  const headerRows = headerLines.map((row) => [row.label, row.value]);
  autoTable(pdf, {
    startY: y,
    margin: { right: margin, left: margin, top: margin, bottom: 15 },
    body: headerRows,
    theme: 'plain',
    styles: {
      font: activeFont,
      fontSize: 8.5,
      cellPadding: 1.2,
      textColor: [17, 24, 39],
      lineColor: [17, 24, 39],
      lineWidth: 0,
    },
    columnStyles: {
      0: {
        cellWidth: 38,
        fontStyle: safeTableFontStyle(activeFont),
        textColor: [27, 59, 135],
      },
      1: { cellWidth: 'auto' },
    },
    didDrawCell: (data: {
      section?: string;
      column: { index: number };
      row: { index: number };
    }) => {
      if (data.section !== 'body' || data.column.index !== 1) return;
      // underline the value cell on the value baseline
      const cell = data as unknown as {
        cell: { x: number; y: number; width: number; height: number };
      };
      const baseline = cell.cell.y + cell.cell.height - 1.5;
      pdf.setDrawColor(17, 24, 39);
      pdf.setLineWidth(0.2);
      pdf.line(cell.cell.x, baseline, cell.cell.x + cell.cell.width, baseline);
    },
  });
  y = pdfWithTable.lastAutoTable.finalY + 4;

  // Instructional / scale legend ---------------------------------------
  pdf.setFontSize(8);
  applyFont(pdf, activeFont, 'bold');
  pdf.setTextColor(27, 59, 135);
  pdf.text('Scale:', margin, y);
  pdf.setTextColor(17, 24, 39);
  applyFont(pdf, activeFont, 'normal');
  pdf.text(
    '4 = Very Satisfactory, 3 = Satisfactory, 2 = Needs Improvement, 1 = Poor (1-4 scale).',
    margin + 11,
    y,
  );
  y += 6;

  // Criteria rubric table ----------------------------------------------
  const criteriaRows = domainData.criteria.map((row, index) => {
    const ungroundedMarker = row.is_ungrounded ? ' [Ungrounded]' : '';
    const text =
      (cleanJustification(row.criterion_text) || '(criterion text unavailable)') + ungroundedMarker;
    return [
      String(index + 1),
      text,
      row.score === 4 ? 'X' : '',
      row.score === 3 ? 'X' : '',
      row.score === 2 ? 'X' : '',
      row.score === 1 ? 'X' : '',
    ];
  });
  autoTable(pdf, {
    startY: y,
    margin: { top: margin, right: margin, bottom: 15, left: margin },
    head: [[{ content: config.sectionTitle, colSpan: 2 }, '4', '3', '2', '1']],
    body: criteriaRows,
    theme: 'grid',
    styles: {
      font: activeFont,
      fontSize: 7.5,
      cellPadding: 1.7,
      lineColor: [17, 24, 39],
      lineWidth: 0.2,
      textColor: [17, 24, 39],
      valign: 'middle',
    },
    headStyles: {
      fillColor: [240, 244, 248],
      fontStyle: safeTableFontStyle(activeFont),
      halign: 'center',
      textColor: [17, 24, 39],
    },
    columnStyles: {
      0: { cellWidth: 8, halign: 'center' },
      1: { cellWidth: 'auto' },
      2: { cellWidth: 10, halign: 'center' },
      3: { cellWidth: 10, halign: 'center' },
      4: { cellWidth: 10, halign: 'center' },
      5: { cellWidth: 10, halign: 'center' },
    },
  });
  y = ensureRoom(pdf, pdfWithTable.lastAutoTable.finalY + 6, 24, margin);

  // Score summary banner -----------------------------------------------
  // Two distinct values: 1-4 subtotal and 0-100 monitoring %. They are
  // always shown side by side and never combined into a single aggregate.
  pdf.setFontSize(9.5);
  applyFont(pdf, activeFont, 'bold');
  pdf.setTextColor(27, 59, 135);
  pdf.text(`Subtotal (1-4 scale): ${formatScore(subtotal)} / ${formatScore(maxScore)}`, margin, y);
  applyFont(pdf, activeFont, 'normal');
  pdf.setTextColor(17, 24, 39);
  pdf.text(`   Adjectival rating: ${rating}`, margin + 65, y);
  y += 6;
  pdf.setFontSize(9.5);
  applyFont(pdf, activeFont, 'bold');
  pdf.setTextColor(27, 59, 135);
  pdf.text(`Monitoring % (0-100 scale): ${monitoring}%`, margin, y);
  pdf.setTextColor(17, 24, 39);
  applyFont(pdf, activeFont, 'normal');
  pdf.setFontSize(7.5);
  pdf.text(
    'Buckets: 3.50-4.00 = Very Satisfactory; 2.50-3.49 = Satisfactory; 1.50-2.49 = Needs Improvement; 1.00-1.49 = Poor.',
    margin,
    y + 4,
  );
  y += 10;

  // Comments / suggestions ---------------------------------------------
  const comments = buildComments(domainData) || 'Not provided.';
  y = ensureRoom(pdf, y, 28, margin);
  autoTable(pdf, {
    startY: y,
    margin: { top: margin, right: margin, bottom: 18, left: margin },
    head: [['Additional Comments / Suggestions:']],
    body: [[comments || ' ']],
    theme: 'grid',
    styles: {
      font: activeFont,
      fontSize: 8,
      cellPadding: 2.5,
      lineColor: [17, 24, 39],
      lineWidth: 0.2,
      textColor: [17, 24, 39],
      minCellHeight: 18,
    },
    headStyles: {
      fillColor: [240, 244, 248],
      fontStyle: safeTableFontStyle(activeFont),
      textColor: [17, 24, 39],
    },
  });
  y = ensureRoom(pdf, pdfWithTable.lastAutoTable.finalY + 16, 18, margin);

  // Signature block (kept intentionally blank - never auto-fill names) -
  pdf.setDrawColor(17, 24, 39);
  pdf.setLineWidth(0.2);
  pdf.line(margin, y, margin + 60, y);
  pdf.line(pageWidth - margin - 60, y, pageWidth - margin, y);
  applyFont(pdf, activeFont, 'normal');
  pdf.setFontSize(8);
  pdf.text('Signature over Printed Name (Reviewer)', margin, y + 4);
  pdf.text('Date Evaluated', pageWidth - margin - 60, y + 4);

  // Footer --------------------------------------------------------------
  const pageCount = pdf.getNumberOfPages();
  for (let page = 1; page <= pageCount; page += 1) {
    pdf.setPage(page);
    pdf.setFontSize(7.5);
    applyFont(pdf, activeFont, 'normal');
    pdf.setTextColor(71, 85, 105);
    pdf.text(config.code, margin, 289);
    pdf.text('EquipED - LSPU SCC', pageWidth / 2, 289, { align: 'center' });
    pdf.text('Advisory only - Human review authoritative', pageWidth - margin, 289, {
      align: 'right',
    });
  }

  const safeAgent = (domainData.agentId || 'agent').toString().replace(/[^a-z0-9_-]/gi, '-');
  pdf.save(`${config.code}-${safeAgent}-evaluation.pdf`);
}

function getExportDomainData({
  domainData,
  agentId = 'gad',
}: ExportDocumentProps): ExportDomainData {
  return (
    domainData ?? {
      agentId,
      criteria: [],
      subtotal: 0,
      max_score: CANONICAL_MAX_SCORE,
      status: 'PENDING',
    }
  );
}

export function GadExportDownloadButton(props: ExportDocumentProps) {
  const domainData = getExportDomainData(props);
  const [isDownloading, setIsDownloading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleDownload = async () => {
    setIsDownloading(true);
    setErrorMessage(null);
    try {
      await downloadExport(domainData);
    } catch (error) {
      console.error('Unable to create the per-agent evaluation PDF.', error);
      setErrorMessage('PDF export failed. Please try again.');
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="inline-flex flex-col items-start gap-1">
      <button
        type="button"
        className="inline-flex h-9 items-center justify-center bg-primary hover:bg-primary-strong text-primary-foreground px-4 rounded-sm text-xs font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-ring focus:outline-none disabled:opacity-60"
        onClick={handleDownload}
        disabled={isDownloading}
      >
        <DownloadSimple className="size-4 mr-1.5" aria-hidden="true" />
        {isDownloading ? 'Creating PDF...' : 'Download PDF'}
      </button>
      {errorMessage && (
        <span className="text-xs font-medium text-destructive" role="alert">
          {errorMessage}
        </span>
      )}
    </div>
  );
}

export function GadExportPreview(props: ExportDocumentProps) {
  const domainData = getExportDomainData(props);
  const config = AGENT_CONFIGS[domainData.agentId] || {
    code: 'LSPU-CID-SF-004',
    sectionTitle: 'EVALUATION CRITERIA',
    unitName: domainData.agentId.toString().toUpperCase(),
  };
  const subtotal = Number.isFinite(domainData.subtotal) ? domainData.subtotal : 0;
  const maxScore =
    Number.isFinite(domainData.max_score) && domainData.max_score > 0
      ? domainData.max_score
      : CANONICAL_MAX_SCORE;
  const rating = domainData.adjectival_rating || adjectivalRating(subtotal);
  const monitoring = monitoringPercentage(subtotal, maxScore);
  const comments = buildComments(domainData);
  const headerLines = buildHeaderLines(domainData);

  return (
    <div className="mx-auto min-h-[297mm] w-full max-w-4xl overflow-auto border border-border bg-surface p-6 sm:p-10 text-xs text-text shadow-sm rounded-md space-y-6">
      {/* Institutional Letterhead */}
      <div className="flex items-center justify-center gap-4 pb-4 border-b border-border">
        <img
          className="size-16 object-contain"
          src={`${(import.meta.env?.BASE_URL as string | undefined) ?? '/'}lspu-logo.png`}
          alt="LSPU logo"
        />
        <div className="text-center">
          <div className="text-xs font-medium text-text-muted">Republic of the Philippines</div>
          <div className="text-sm font-bold text-text">Laguna State Polytechnic University</div>
          <div className="text-xs text-text-muted">Curriculum and Instruction Division · Gender and Development Unit</div>
        </div>
      </div>

      <div className="text-center space-y-1">
        <h2 className="text-sm font-bold uppercase tracking-wider text-text">
          Criteria for Evaluation of Instructional Materials
        </h2>
        <p className="text-xs font-semibold text-primary uppercase tracking-wide">
          {config.code} · {config.unitName} Review Form
        </p>
      </div>

      {domainData.isPartial && (
        <div className="rounded-sm border border-warning/30 bg-warning-soft p-3 text-xs text-warning">
          <p className="font-bold uppercase tracking-wider">
            Partial evaluation - Advisory only
          </p>
          {domainData.partialReason && <p className="mt-0.5">{domainData.partialReason}</p>}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-2 text-xs border border-border rounded-sm p-4 bg-surface-subtle">
        {headerLines.map((row) => (
          <div key={row.label} className="flex items-baseline justify-between border-b border-border/60 pb-1">
            <span className="font-semibold text-text-muted">{row.label}:</span>
            <span className="font-bold text-text truncate max-w-[14rem]">{row.value}</span>
          </div>
        ))}
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <span className="font-semibold text-text">GAD Rubric Evaluation Matrix</span>
          <span className="text-text-muted">
            Scale: <strong>4</strong> = Very Satisfactory, <strong>3</strong> = Satisfactory, <strong>2</strong> = Needs Improvement, <strong>1</strong> = Poor
          </span>
        </div>

        <div className="overflow-x-auto rounded-sm border border-border">
          <table className="w-full text-left border-collapse text-xs">
            <thead className="bg-surface-subtle border-b border-border text-[11px] font-bold uppercase tracking-wider text-text-muted">
              <tr>
                <th scope="col" className="w-10 p-2.5 text-center border-r border-border">#</th>
                <th scope="col" className="p-2.5 border-r border-border">{config.sectionTitle}</th>
                <th scope="col" className="w-10 p-2.5 text-center border-r border-border">4</th>
                <th scope="col" className="w-10 p-2.5 text-center border-r border-border">3</th>
                <th scope="col" className="w-10 p-2.5 text-center border-r border-border">2</th>
                <th scope="col" className="w-10 p-2.5 text-center">1</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-surface">
              {domainData.criteria.map((row, idx) => (
                <tr key={row.criterion_id || idx} className="hover:bg-surface-subtle/50">
                  <td className="w-10 p-2.5 text-center font-mono font-bold text-text-muted border-r border-border tabular-nums">
                    {idx + 1}
                  </td>
                  <td className="p-2.5 text-text font-medium border-r border-border">
                    {cleanJustification(row.criterion_text)}
                  </td>
                  {['4', '3', '2', '1'].map((rating) => (
                    <td key={rating} className={cn("w-10 p-2.5 text-center font-bold border-r border-border last:border-r-0", row.score.toString() === rating ? 'text-primary bg-primary-soft/30' : 'text-transparent')}>
                      {row.score.toString() === rating ? '✓' : ''}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="rounded-sm border border-border p-4 bg-surface-subtle space-y-2 text-xs">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <span className="font-semibold text-text-muted">Subtotal (1-4 scale): </span>
            <strong className="text-text tabular-nums">{formatScore(subtotal)} / {formatScore(maxScore)}</strong>
          </div>
          <div>
            <span className="font-semibold text-text-muted">Adjectival Rating: </span>
            <strong className="text-text">{rating}</strong>
          </div>
          <div>
            <span className="font-semibold text-text-muted">Monitoring Score: </span>
            <strong className="text-primary tabular-nums">{monitoring}%</strong>
          </div>
        </div>
      </div>

      <div className="space-y-1.5 text-xs">
        <span className="font-bold text-text uppercase tracking-wider">
          Specialist Comments & Actionable Recommendations:
        </span>
        <div className="min-h-16 rounded-sm border border-border bg-surface p-3 text-xs leading-relaxed text-text">
          {comments || 'All evaluated criteria verified compliant.'}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-12 text-center text-xs pt-8 border-t border-border">
        <div className="border-t border-border pt-1.5 font-medium text-text">
          GAD Focal Person / Evaluator Signature
        </div>
        <div className="border-t border-border pt-1.5 font-medium text-text">
          Date Verified
        </div>
      </div>

      <div className="flex items-center justify-between text-[10px] text-text-muted border-t border-border pt-2">
        <span>{config.code}</span>
        <span>EquipED Quality Assurance · LSPU Santa Cruz Campus</span>
        <span>Advisory Instrument</span>
      </div>
    </div>
  );
}
