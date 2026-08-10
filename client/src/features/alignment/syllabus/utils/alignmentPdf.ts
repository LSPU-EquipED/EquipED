import type { jsPDF as JsPdfDocument } from 'jspdf';
import type { AlignmentRun } from '../types';
import { levelLabels } from './alignmentPresentation';

type AutoTablePlugin = (pdf: JsPdfDocument, options: Record<string, unknown>) => void;

const MARGIN = 12;
const PAGE_BOTTOM = 278;
const BLUE: [number, number, number] = [27, 59, 135];
const SLATE: [number, number, number] = [30, 41, 59];
const GRID: [number, number, number] = [148, 163, 184];

function formatDate(value?: string | null) {
  if (!value) return 'Unavailable';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('en-PH');
}

function safeFilename(value: string) {
  return value.replace(/[\\/:*?"<>|]+/g, '-').replace(/\s+/g, ' ').trim();
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

export async function exportAlignmentPdf(run: AlignmentRun): Promise<void> {
  if (!run.alignment_artifact || !run.alignment_level) return;
  const [{ jsPDF }, autoTableModule, logoDataUrl] = await Promise.all([
    import('jspdf'),
    import('jspdf-autotable'),
    loadLogoDataUrl(),
  ]);
  const autoTable = (autoTableModule.default || autoTableModule) as unknown as AutoTablePlugin;
  const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  drawAlignmentPdf(pdf, run, autoTable, logoDataUrl);
  pdf.save(`${safeFilename(run.slm_title || 'SLM')}-CID-syllabus-alignment.pdf`);
}

export function drawAlignmentPdf(
  pdf: JsPdfDocument,
  run: AlignmentRun,
  autoTable: AutoTablePlugin,
  logoDataUrl: string | null = null,
): void {
  const artifact = run.alignment_artifact;
  if (!artifact || !run.alignment_level) return;
  const pageWidth = pdf.internal.pageSize.getWidth();
  const contentWidth = pageWidth - MARGIN * 2;
  const pdfWithTable = pdf as JsPdfDocument & { lastAutoTable: { finalY: number } };
  let y = 12;

  pdf.setTextColor(...SLATE);
  if (logoDataUrl) {
    try {
      pdf.addImage(logoDataUrl, 'PNG', MARGIN, y, 20, 20);
    } catch {
      // The formal text header remains usable when an image reader rejects the logo.
    }
  }
  pdf.setFont('helvetica', 'normal');
  pdf.setFontSize(9);
  pdf.text('Republic of the Philippines', pageWidth / 2, y + 3, { align: 'center' });
  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(11);
  pdf.text('LAGUNA STATE POLYTECHNIC UNIVERSITY', pageWidth / 2, y + 9, {
    align: 'center',
  });
  pdf.setFontSize(9);
  pdf.text('SANTA CRUZ CAMPUS', pageWidth / 2, y + 14, { align: 'center' });
  pdf.setFont('helvetica', 'normal');
  pdf.setFontSize(8);
  pdf.text('Curriculum Instruction Development Office', pageWidth / 2, y + 19, {
    align: 'center',
  });
  y += 28;

  pdf.setDrawColor(...BLUE);
  pdf.setLineWidth(0.5);
  pdf.line(MARGIN, y, pageWidth - MARGIN, y);
  y += 7;
  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(14);
  pdf.setTextColor(...BLUE);
  pdf.text('SYLLABUS ALIGNMENT REVIEW FORM', pageWidth / 2, y, { align: 'center' });
  y += 5;
  pdf.setFont('helvetica', 'normal');
  pdf.setFontSize(8);
  pdf.setTextColor(71, 85, 105);
  pdf.text('EquipED advisory review copy for CID verification', pageWidth / 2, y, {
    align: 'center',
  });
  y += 7;

  autoTable(pdf, {
    startY: y,
    margin: { left: MARGIN, right: MARGIN },
    body: [
      ['SLM title', run.slm_title || 'Not available'],
      ['Reference syllabus', run.syllabus_title || 'Not available'],
      ['Alignment reference', run.alignment_id],
      ['Date evaluated', formatDate(run.completed_at)],
      ['Alignment level', levelLabels[run.alignment_level].toUpperCase()],
      ['Topic coverage', `${artifact.aligned_topics} of ${artifact.total_topics} topics aligned`],
    ],
    theme: 'grid',
    styles: {
      font: 'helvetica',
      fontSize: 8,
      cellPadding: 2,
      lineColor: GRID,
      lineWidth: 0.2,
      textColor: SLATE,
      valign: 'middle',
    },
    columnStyles: {
      0: {
        cellWidth: 42,
        fontStyle: 'bold',
        fillColor: [248, 250, 252],
        textColor: BLUE,
      },
      1: { cellWidth: 'auto' },
    },
  });
  y = pdfWithTable.lastAutoTable.finalY + 7;

  pdf.setFillColor(239, 246, 255);
  pdf.setDrawColor(...BLUE);
  pdf.roundedRect(MARGIN, y, contentWidth, 20, 1, 1, 'FD');
  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(10);
  pdf.setTextColor(...BLUE);
  pdf.text(`RESULT: ${levelLabels[run.alignment_level].toUpperCase()}`, MARGIN + 4, y + 7);
  pdf.setFont('helvetica', 'normal');
  pdf.setFontSize(8.5);
  pdf.setTextColor(...SLATE);
  pdf.text(
    `${artifact.aligned_topics} aligned topic(s) / ${artifact.total_topics} substantial topic(s) reviewed`,
    MARGIN + 4,
    y + 14,
  );
  y += 27;

  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(10);
  pdf.setTextColor(...BLUE);
  pdf.text('JUSTIFICATION', MARGIN, y);
  y += 3;
  const justificationLines = pdf.splitTextToSize(
    run.justification || 'No detailed justification was recorded.',
    contentWidth - 8,
  );
  const justificationHeight = Math.max(18, justificationLines.length * 4 + 8);
  pdf.setDrawColor(...GRID);
  pdf.rect(MARGIN, y, contentWidth, justificationHeight);
  pdf.setFont('helvetica', 'normal');
  pdf.setFontSize(8.5);
  pdf.setTextColor(...SLATE);
  pdf.text(justificationLines, MARGIN + 4, y + 6);
  y += justificationHeight + 7;

  const topicRows = [
    ...artifact.content_matches.map((item, index) => [
      String(index + 1),
      item.topic,
      `Page ${item.slm_page_number ?? '-'}: ${item.slm_evidence}`,
      `${item.content_ref || 'Course content'}, page ${item.page_number ?? '-'}: ${item.content_text}`,
      `ALIGNED\n${item.rationale}`,
    ]),
    ...artifact.unmatched_topics.map((item, index) => [
      String(artifact.content_matches.length + index + 1),
      item.topic,
      `Page ${item.slm_page_number ?? '-'}: ${item.slm_evidence}`,
      'No supported course-content match',
      `OUTSIDE SYLLABUS\n${item.rationale}`,
    ]),
  ];

  autoTable(pdf, {
    startY: y,
    margin: { top: MARGIN, left: MARGIN, right: MARGIN, bottom: 20 },
    head: [['No.', 'SLM topic', 'SLM evidence', 'Syllabus evidence', 'Finding']],
    body: topicRows.length
      ? topicRows
      : [['-', 'No topics recorded', '-', '-', 'UNAVAILABLE']],
    theme: 'grid',
    styles: {
      font: 'helvetica',
      fontSize: 6.8,
      cellPadding: 1.6,
      lineColor: GRID,
      lineWidth: 0.2,
      textColor: SLATE,
      valign: 'top',
      overflow: 'linebreak',
    },
    headStyles: {
      fillColor: BLUE,
      textColor: [255, 255, 255],
      fontStyle: 'bold',
      fontSize: 7.2,
      halign: 'center',
    },
    columnStyles: {
      0: { cellWidth: 9, halign: 'center' },
      1: { cellWidth: 34 },
      2: { cellWidth: 43 },
      3: { cellWidth: 48 },
      4: { cellWidth: 'auto' },
    },
    didParseCell: (data: {
      section?: string;
      column?: { index: number };
      cell: { raw?: unknown; styles: Record<string, unknown> };
    }) => {
      if (data.section !== 'body' || data.column?.index !== 4) return;
      const finding = String(data.cell.raw ?? '');
      data.cell.styles.fontStyle = 'bold';
      data.cell.styles.textColor = finding.startsWith('ALIGNED')
        ? [36, 107, 41]
        : [185, 28, 28];
    },
  });
  y = pdfWithTable.lastAutoTable.finalY + 8;

  if (y + 38 > PAGE_BOTTOM) {
    pdf.addPage();
    y = MARGIN;
  }
  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(9);
  pdf.setTextColor(...BLUE);
  pdf.text('CID HUMAN REVIEW', MARGIN, y);
  y += 5;
  pdf.setFont('helvetica', 'normal');
  pdf.setFontSize(8);
  pdf.setTextColor(...SLATE);
  pdf.text(
    'This automated alignment is advisory only. The authorized CID reviewer retains final authority.',
    MARGIN,
    y,
  );
  y += 16;
  pdf.setDrawColor(...GRID);
  pdf.line(MARGIN, y, MARGIN + 62, y);
  pdf.line(MARGIN + 72, y, MARGIN + 134, y);
  pdf.line(MARGIN + 144, y, pageWidth - MARGIN, y);
  pdf.setFontSize(7.5);
  pdf.setTextColor(71, 85, 105);
  pdf.text('Reviewed by / Signature', MARGIN, y + 4);
  pdf.text('CID remarks', MARGIN + 72, y + 4);
  pdf.text('Date', MARGIN + 144, y + 4);

  const pageCount = pdf.getNumberOfPages();
  for (let page = 1; page <= pageCount; page += 1) {
    pdf.setPage(page);
    pdf.setDrawColor(226, 232, 240);
    pdf.line(MARGIN, 283, pageWidth - MARGIN, 283);
    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(7);
    pdf.setTextColor(100, 116, 139);
    pdf.text('LSPU SCC - Curriculum Instruction Development Office', MARGIN, 288);
    pdf.text(`Page ${page} of ${pageCount}`, pageWidth - MARGIN, 288, { align: 'right' });
  }
}
