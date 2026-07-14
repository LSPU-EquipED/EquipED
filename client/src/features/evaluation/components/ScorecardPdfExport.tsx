import { useState } from 'react';
import { Download } from 'lucide-react';
import type { jsPDF as JsPdfDocument } from 'jspdf';
import type { EvaluationResultsResponse } from '../types';
import { formatScore } from './scoreHelpers';

type ScorecardPdfExportProps = {
  results: EvaluationResultsResponse;
};

const DOMAIN_LABELS: Record<string, string> = {
  sme: 'Subject Matter Expert (SME)',
  coordinator: 'Program Coordinator',
  gad: 'Gender and Development (GAD)',
  itso: 'Innovation and Technology Support Office (ITSO)',
};

const DOMAIN_ORDER = ['sme', 'coordinator', 'gad', 'itso'];

async function loadLogoDataUrl(): Promise<string> {
  const response = await fetch(`${import.meta.env.BASE_URL}lspu-logo.png`);

  if (!response.ok) {
    throw new Error('The LSPU logo could not be loaded.');
  }

  const blob = await response.blob();

  return await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error('The LSPU logo could not be read.'));
    reader.readAsDataURL(blob);
  });
}

function getCriterionStatus(score: number): string {
  if (score >= 3) return 'Strong';
  if (score >= 2) return 'Moderate';
  return 'Needs attention';
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

async function exportScorecardPdf(results: EvaluationResultsResponse): Promise<void> {
  const [{ jsPDF }, { default: autoTable }] = await Promise.all([
    import('jspdf'),
    import('jspdf-autotable'),
  ]);
  const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  const pdfWithTable = pdf as JsPdfDocument & { lastAutoTable: { finalY: number } };
  const logo = await loadLogoDataUrl();
  const pageWidth = pdf.internal.pageSize.getWidth();
  const margin = 12;
  const contentWidth = pageWidth - margin * 2;

  pdf.setTextColor(30, 41, 59);
  pdf.addImage(logo, 'PNG', 43, 10, 20, 20);
  pdf.setFont('helvetica', 'normal');
  pdf.setFontSize(9);
  pdf.text('Republic of the Philippines', 121, 15, { align: 'center' });
  pdf.setFont('helvetica', 'bold');
  pdf.text('Laguna State Polytechnic University', 121, 20, { align: 'center' });
  pdf.setFont('helvetica', 'normal');
  pdf.text('San Pablo City Campus', 121, 25, { align: 'center' });

  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(14);
  pdf.setTextColor(27, 59, 135);
  pdf.text('EVALUATION SCORECARD', pageWidth / 2, 38, { align: 'center' });
  pdf.setFontSize(9);
  pdf.setTextColor(30, 41, 59);
  pdf.text('SLM Multi-Agent Evaluation Summary', pageWidth / 2, 43, { align: 'center' });

  autoTable(pdf, {
    startY: 49,
    margin: { right: margin, left: margin },
    body: [
      ['Document', results.document_title || results.document_id],
      ['Evaluation ID', results.evaluation_id],
      ['Program', results.program || 'Not specified'],
      ['Status', results.is_partial ? 'Partial evaluation' : results.evaluation_status],
      ['Completed', formatTimestamp(results.completed_at)],
    ],
    theme: 'grid',
    styles: {
      font: 'helvetica',
      fontSize: 8,
      cellPadding: 2,
      lineColor: [203, 213, 225],
      lineWidth: 0.2,
      textColor: [30, 41, 59],
    },
    columnStyles: {
      0: { cellWidth: 32, fontStyle: 'bold', fillColor: [248, 250, 252] },
      1: { cellWidth: 'auto' },
    },
  });

  let y = pdfWithTable.lastAutoTable.finalY + 6;
  pdf.setFillColor(239, 246, 255);
  pdf.setDrawColor(27, 59, 135);
  pdf.roundedRect(margin, y, contentWidth, 17, 1, 1, 'FD');
  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(10);
  pdf.setTextColor(27, 59, 135);
  pdf.text(
    `Overall score: ${formatScore(results.overall_score ?? results.synthesized_score)} of 4`,
    margin + 3,
    y + 6,
  );
  pdf.setFontSize(8.5);
  pdf.text(`Rating: ${results.adjectival_rating || 'Not available'}`, margin + 3, y + 12);
  pdf.setFont('helvetica', 'normal');
  pdf.setTextColor(30, 41, 59);
  pdf.text('Advisory only - Human review is authoritative.', pageWidth - margin - 3, y + 9, {
    align: 'right',
  });
  y += 23;

  if (results.is_partial && results.partial_reason) {
    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(8.5);
    pdf.text('Partial evaluation notice', margin, y);
    pdf.setFont('helvetica', 'normal');
    const partialLines = pdf.splitTextToSize(results.partial_reason, contentWidth);
    pdf.text(partialLines, margin, y + 5);
    y += 7 + partialLines.length * 3.5;
  }

  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(10);
  pdf.text('Agent score summary', margin, y);
  y += 3;

  const summaryRows = DOMAIN_ORDER.map((domain) => {
    const score = results.domain_scores[domain];
    if (!score) {
      const status = results.failed_agents.includes(domain)
        ? 'Failed'
        : results.is_partial && domain === 'coordinator'
          ? 'Skipped'
          : 'Unavailable';
      return [DOMAIN_LABELS[domain], '-', '-', status];
    }

    const percent = Math.round((score.subtotal / (score.max_score || 1)) * 100);
    return [
      DOMAIN_LABELS[domain],
      `${formatScore(score.subtotal)} / ${formatScore(score.max_score)}`,
      `${percent}%`,
      score.adjectival_rating || score.status,
    ];
  });

  autoTable(pdf, {
    startY: y,
    margin: { top: margin, right: margin, bottom: 15, left: margin },
    head: [['Review domain', 'Weighted subtotal', 'Score', 'Rating / status']],
    body: summaryRows,
    theme: 'grid',
    styles: {
      font: 'helvetica',
      fontSize: 7.5,
      cellPadding: 2,
      lineColor: [148, 163, 184],
      lineWidth: 0.2,
      textColor: [30, 41, 59],
      valign: 'middle',
    },
    headStyles: { fillColor: [27, 59, 135], textColor: [255, 255, 255], fontStyle: 'bold' },
    columnStyles: {
      0: { cellWidth: 72 },
      1: { cellWidth: 35, halign: 'center' },
      2: { cellWidth: 25, halign: 'center' },
      3: { cellWidth: 'auto' },
    },
  });

  for (const domain of DOMAIN_ORDER) {
    const domainData = results.domain_scores[domain];
    if (!domainData?.criteria.length) continue;

    y = pdfWithTable.lastAutoTable.finalY + 8;
    if (y > 255) {
      pdf.addPage('a4', 'portrait');
      y = margin;
    }

    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(10);
    pdf.setTextColor(27, 59, 135);
    pdf.text(DOMAIN_LABELS[domain], margin, y);

    autoTable(pdf, {
      startY: y + 3,
      margin: { top: margin, right: margin, bottom: 15, left: margin },
      head: [['#', 'Criterion', 'Score', 'Status', 'Evaluation notes']],
      body: domainData.criteria.map((criterion, index) => [
        String(index + 1),
        criterion.criterion_text,
        `${formatScore(criterion.score)}/4`,
        getCriterionStatus(criterion.score),
        criterion.justification || criterion.evidence || '-',
      ]),
      theme: 'grid',
      styles: {
        font: 'helvetica',
        fontSize: 7,
        cellPadding: 1.8,
        lineColor: [148, 163, 184],
        lineWidth: 0.2,
        textColor: [30, 41, 59],
        valign: 'top',
      },
      headStyles: {
        fillColor: [248, 250, 252],
        textColor: [30, 41, 59],
        fontStyle: 'bold',
      },
      columnStyles: {
        0: { cellWidth: 8, halign: 'center' },
        1: { cellWidth: 57 },
        2: { cellWidth: 16, halign: 'center' },
        3: { cellWidth: 25 },
        4: { cellWidth: 'auto' },
      },
    });
  }

  if (results.flags.length > 0) {
    y = pdfWithTable.lastAutoTable.finalY + 8;
    if (y > 255) {
      pdf.addPage('a4', 'portrait');
      y = margin;
    }

    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(10);
    pdf.setTextColor(185, 28, 28);
    pdf.text('Items requiring human attention', margin, y);

    autoTable(pdf, {
      startY: y + 3,
      margin: { top: margin, right: margin, bottom: 15, left: margin },
      head: [['Agent', 'Score', 'Criterion', 'Reason']],
      body: results.flags.map((flag) => [
        DOMAIN_LABELS[flag.agent_id] || flag.agent_id.toUpperCase(),
        `${formatScore(flag.score)}/4`,
        flag.criterion_text,
        flag.justification || '-',
      ]),
      theme: 'grid',
      styles: {
        font: 'helvetica',
        fontSize: 7,
        cellPadding: 1.8,
        lineColor: [148, 163, 184],
        lineWidth: 0.2,
        textColor: [30, 41, 59],
        valign: 'top',
      },
      headStyles: { fillColor: [185, 28, 28], textColor: [255, 255, 255] },
      columnStyles: {
        0: { cellWidth: 39 },
        1: { cellWidth: 15, halign: 'center' },
        2: { cellWidth: 58 },
        3: { cellWidth: 'auto' },
      },
    });
  }

  const pageCount = pdf.getNumberOfPages();
  for (let page = 1; page <= pageCount; page += 1) {
    pdf.setPage(page);
    pdf.setDrawColor(226, 232, 240);
    pdf.line(margin, 283, pageWidth - margin, 283);
    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(7.5);
    pdf.setTextColor(71, 85, 105);
    pdf.text('EquipED - LSPU SCC', margin, 289);
    pdf.text(`Page ${page} of ${pageCount}`, pageWidth / 2, 289, { align: 'center' });
    pdf.text('Human review authoritative', pageWidth - margin, 289, { align: 'right' });
  }

  pdf.save(`EquipED-scorecard-${results.evaluation_id}.pdf`);
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
