import { useState } from 'react';
import { Download } from 'lucide-react';
import type { jsPDF as JsPdfDocument } from 'jspdf';
import type { DomainScoreBlock } from '../types';

export type ExportAgentId = 'coordinator' | 'sme' | 'gad' | 'itso';

export type ExportDomainData = DomainScoreBlock & {
  agentId: ExportAgentId;
  documentTitle?: string;
  program?: string;
};

type ExportDocumentProps = {
  readonly domainData?: ExportDomainData;
  readonly agentId?: ExportAgentId;
};

const AGENT_CONFIGS: Record<
  ExportAgentId,
  { code: string; sectionTitle: string; unitName: string }
> = {
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

function getExportTotal(domainData: ExportDomainData) {
  return domainData.subtotal;
}

function getExportAverage(domainData: ExportDomainData) {
  if (!domainData.criteria || domainData.criteria.length === 0) return 0;
  return domainData.subtotal / domainData.criteria.length;
}

function getAdjectivalRating(average: number) {
  if (average >= 3.5) {
    return 'Very Satisfactory';
  }

  if (average >= 2.5) {
    return 'Satisfactory';
  }

  if (average >= 1.5) {
    return 'Needs Improvement';
  }

  return 'Poor';
}

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

async function downloadExport(domainData: ExportDomainData) {
  const [{ jsPDF }, { default: autoTable }] = await Promise.all([
    import('jspdf'),
    import('jspdf-autotable'),
  ]);
  const config = AGENT_CONFIGS[domainData.agentId] || {
    code: 'N/A',
    sectionTitle: 'EVALUATION CRITERIA',
    unitName: domainData.agentId.toUpperCase(),
  };
  const total = getExportTotal(domainData);
  const average = getExportAverage(domainData);
  const adjectivalRating = getAdjectivalRating(average);
  const comments = domainData.criteria
    .filter((c) => c.justification)
    .map((c) => c.justification)
    .join('\n\n');
  const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  const pdfWithTable = pdf as JsPdfDocument & { lastAutoTable: { finalY: number } };
  const pageWidth = pdf.internal.pageSize.getWidth();
  const margin = 12;
  const contentWidth = pageWidth - margin * 2;
  const logo = await loadLogoDataUrl();

  pdf.addImage(logo, 'PNG', 46, 10, 20, 20);
  pdf.setTextColor(17, 24, 39);
  pdf.setFont('helvetica', 'normal');
  pdf.setFontSize(9);
  pdf.text('Republic of the Philippines', 122, 15, { align: 'center' });
  pdf.setFont('helvetica', 'bold');
  pdf.text('Laguna State Polytechnic University', 122, 20, { align: 'center' });
  pdf.setFont('helvetica', 'normal');
  pdf.text('Province of Laguna', 122, 25, { align: 'center' });

  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(11);
  pdf.text('CRITERIA FOR EVALUATION OF INSTRUCTIONAL MATERIALS', pageWidth / 2, 37, {
    align: 'center',
  });
  pdf.text(`FOR ${config.unitName}`, pageWidth / 2, 42, { align: 'center' });

  const drawField = (label: string, value: string, x: number, y: number, width: number) => {
    pdf.setFontSize(8.5);
    pdf.setFont('helvetica', 'normal');
    pdf.text(label, x, y);
    const labelWidth = pdf.getTextWidth(label) + 1.5;
    const valueX = x + labelWidth;
    const [fittedValue = ''] = pdf.splitTextToSize(value, width - labelWidth);
    pdf.text(fittedValue, valueX, y);
    pdf.line(valueX, y + 1, x + width, y + 1);
  };

  drawField('Name of Faculty:', 'Faculty Reviewer', margin, 51, 91);
  drawField('College:', 'LSPU SCC', 110, 51, 88);
  drawField(
    'Course Title:',
    domainData.documentTitle || 'Outcomes-Based Learning Module',
    margin,
    58,
    91,
  );
  drawField('Semester:', '1st', 110, 58, 88);
  drawField('Academic Year:', '2025-2026', margin, 65, 91);

  pdf.setFontSize(8);
  pdf.setFont('helvetica', 'bold');
  pdf.text('Type of Instructional Material:', margin, 72);
  pdf.setFont('helvetica', 'normal');
  pdf.text(
    '[x] Self-paced Learning Module (with OBE Syllabus and Course Guide)   [ ] Others: __________________',
    margin + 39,
    72,
  );

  pdf.setFont('helvetica', 'bold');
  pdf.text('Instruction:', margin, 78);
  pdf.setFont('helvetica', 'normal');
  const instruction =
    'Rate the materials in the column provided using this scale: 4 - Very Satisfactory; 3 - Satisfactory; 2 - Needs Improvement; 1 - Poor';
  pdf.text(pdf.splitTextToSize(instruction, contentWidth - 17), margin + 17, 78);

  autoTable(pdf, {
    startY: 85,
    margin: { top: margin, right: margin, bottom: 15, left: margin },
    head: [[{ content: config.sectionTitle, colSpan: 2 }, '4', '3', '2', '1']],
    body: domainData.criteria.map((row, index) => [
      String(index + 1),
      row.criterion_text,
      row.score === 4 ? 'X' : '',
      row.score === 3 ? 'X' : '',
      row.score === 2 ? 'X' : '',
      row.score === 1 ? 'X' : '',
    ]),
    theme: 'grid',
    styles: {
      font: 'helvetica',
      fontSize: 7.5,
      cellPadding: 1.7,
      lineColor: [17, 24, 39],
      lineWidth: 0.2,
      textColor: [17, 24, 39],
      valign: 'middle',
    },
    headStyles: { fillColor: [255, 255, 255], fontStyle: 'bold', halign: 'center' },
    columnStyles: {
      0: { cellWidth: 8, halign: 'center' },
      1: { cellWidth: 'auto' },
      2: { cellWidth: 10, halign: 'center', fontStyle: 'bold' },
      3: { cellWidth: 10, halign: 'center', fontStyle: 'bold' },
      4: { cellWidth: 10, halign: 'center', fontStyle: 'bold' },
      5: { cellWidth: 10, halign: 'center', fontStyle: 'bold' },
    },
  });

  let y = pdfWithTable.lastAutoTable.finalY + 6;
  if (y > 245) {
    pdf.addPage('a4', 'portrait');
    y = margin;
  }

  pdf.setFontSize(8.5);
  pdf.setFont('helvetica', 'bold');
  pdf.text(
    `Total: ${total}     Total Score/5: ${average.toFixed(2)}     Adjectival Rating: ${adjectivalRating}`,
    margin,
    y,
  );
  y += 6;
  pdf.setFontSize(8);
  pdf.setFont('helvetica', 'normal');
  pdf.text(
    '3.50 - 4.00 = Very Satisfactory; 2.50 - 3.49 = Satisfactory; 1.50 - 2.49 = Needs Improvement; 1.00 - 1.49 = Poor',
    margin,
    y,
  );
  y += 5;

  autoTable(pdf, {
    startY: y,
    margin: { top: margin, right: margin, bottom: 28, left: margin },
    head: [['Additional Comments/Suggestions:']],
    body: [[comments || ' ']],
    theme: 'grid',
    styles: {
      font: 'helvetica',
      fontSize: 8,
      cellPadding: 2.5,
      lineColor: [17, 24, 39],
      lineWidth: 0.2,
      textColor: [17, 24, 39],
      minCellHeight: 16,
    },
    headStyles: { fillColor: [255, 255, 255], fontStyle: 'bold' },
  });

  y = pdfWithTable.lastAutoTable.finalY + 15;
  if (y > 269) {
    pdf.addPage('a4', 'portrait');
    y = 35;
  }

  pdf.line(28, y, 90, y);
  pdf.line(120, y, 182, y);
  pdf.setFontSize(8);
  pdf.setFont('helvetica', 'normal');
  pdf.text('Signature over Printed Name', 59, y + 4, { align: 'center' });
  pdf.text('Date Evaluated', 151, y + 4, { align: 'center' });

  const pageCount = pdf.getNumberOfPages();
  for (let page = 1; page <= pageCount; page += 1) {
    pdf.setPage(page);
    pdf.setFontSize(7.5);
    pdf.text(config.code, margin, 289);
    pdf.text('Rev. 0', pageWidth / 2, 289, { align: 'center' });
    pdf.text('23 May 2022', pageWidth - margin, 289, { align: 'right' });
  }

  pdf.save(`${config.code}-${domainData.agentId}-evaluation.pdf`);
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
      max_score: 0,
      status: 'PENDING',
    }
  );
}

export function GadExportDownloadButton(props: ExportDocumentProps) {
  const domainData = getExportDomainData(props);
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownload = async () => {
    setIsDownloading(true);
    try {
      await downloadExport(domainData);
    } catch (error) {
      console.error('Unable to create the CID evaluation PDF.', error);
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <button
      type="button"
      className="inline-flex h-9 items-center justify-center bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-white px-4 rounded-sm text-xs font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87] focus:outline-none"
      onClick={handleDownload}
      disabled={isDownloading}
    >
      <Download className="size-4 mr-1.5" aria-hidden="true" />
      {isDownloading ? 'Creating PDF...' : 'Download PDF'}
    </button>
  );
}

export function GadExportPreview(props: ExportDocumentProps) {
  const domainData = getExportDomainData(props);
  const config = AGENT_CONFIGS[domainData.agentId] || {
    code: 'N/A',
    sectionTitle: 'EVALUATION CRITERIA',
    unitName: domainData.agentId.toUpperCase(),
  };
  const total = getExportTotal(domainData);
  const average = getExportAverage(domainData);
  const adjectivalRating = getAdjectivalRating(average);

  const comments = domainData.criteria
    .filter((c) => c.justification)
    .map((c) => c.justification)
    .join('\n\n');

  return (
    <div className="mx-auto min-h-[297mm] w-[210mm] resize overflow-auto border border-slate-200 bg-white p-[12mm] text-[11px] text-black">
      <div className="flex items-center justify-center gap-4 leading-5">
        <img
          className="size-20 object-contain"
          src={`${import.meta.env.BASE_URL}lspu-logo.png`}
          alt="LSPU logo"
        />
        <div className="text-center">
          <div>Republic of the Philippines</div>
          <div className="font-semibold">Laguna State Polytechnic University</div>
          <div>Province of Laguna</div>
        </div>
      </div>

      <h2 className="mt-5 text-center text-sm font-bold uppercase tracking-wide">
        Criteria for Evaluation of Instructional Materials
        <br />
        for {config.unitName}
      </h2>

      <div className="mt-5 grid grid-cols-2 gap-x-8 gap-y-2 text-xs">
        <div>
          Name of Faculty:{' '}
          <span className="inline-block min-w-44 border-b border-black">Faculty Reviewer</span>
        </div>
        <div>
          College: <span className="inline-block min-w-32 border-b border-black">LSPU SCC</span>
        </div>
        <div>
          Course Title:{' '}
          <span className="inline-block min-w-44 border-b border-black">
            {domainData.documentTitle || 'Outcomes-Based Learning Module'}
          </span>
        </div>
        <div>
          Semester: <span className="inline-block min-w-24 border-b border-black">1st</span>
        </div>
        <div>
          Academic Year:{' '}
          <span className="inline-block min-w-28 border-b border-black">2025-2026</span>
        </div>
      </div>

      <div className="mt-4 text-xs leading-5">
        <div>
          <strong>Type of Instructional Material:</strong> [x] Self-paced Learning Module (with OBE
          Syllabus and Course Guide)
        </div>
        <div>[ ] Others (Please specify): ____________________________________________</div>
      </div>

      <p className="mt-4 text-xs leading-5">
        <strong>Instruction:</strong> Rate the materials in the column provided by checking and
        using the following scale: 4 - Very Satisfactory; 3 - Satisfactory; 2 - Needs Improvement; 1
        - Poor
      </p>

      <table className="mt-3 w-full border-collapse text-[11px]">
        <thead>
          <tr>
            <th className="border border-black p-2 text-center" colSpan={2}>
              {config.sectionTitle}
            </th>
            <th className="w-10 border border-black p-2 text-center">4</th>
            <th className="w-10 border border-black p-2 text-center">3</th>
            <th className="w-10 border border-black p-2 text-center">2</th>
            <th className="w-10 border border-black p-2 text-center">1</th>
          </tr>
        </thead>
        <tbody>
          {domainData.criteria.map((row, idx) => (
            <tr key={row.criterion_id || idx}>
              <td className="w-8 border border-black p-2 text-center">{idx + 1}</td>
              <td className="border border-black p-2">{row.criterion_text}</td>
              {['4', '3', '2', '1'].map((rating) => (
                <td key={rating} className="border border-black p-2 text-center font-bold">
                  {row.score.toString() === rating ? 'x' : ''}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-4 text-xs leading-5">
        <strong>Total:</strong> {total} <span className="mx-2" />
        <strong>Total Score/5:</strong> {average.toFixed(2)} <span className="mx-2" />
        <strong>Adjectival Rating:</strong> {adjectivalRating}
      </div>

      <p className="mt-3 text-xs leading-5">
        3.50 - 4.00 = Very Satisfactory; 2.50 - 3.49 = Satisfactory; 1.50 - 2.49 = Needs
        Improvement; 1.00 - 1.49 = Poor
      </p>

      <div className="mt-4 text-xs">
        <strong>Additional Comments/Suggestions:</strong>
        <div className="mt-2 min-h-20 border border-black p-2 leading-5 whitespace-pre-wrap">
          {comments}
        </div>
      </div>

      <div className="mt-12 grid grid-cols-2 gap-20 text-center text-xs">
        <div className="border-t border-black pt-2">Signature over Printed Name</div>
        <div className="border-t border-black pt-2">Date Evaluated</div>
      </div>

      <div className="mt-8 flex justify-between text-[10px]">
        <span>{config.code}</span>
        <span>Rev. 0</span>
        <span>23 May 2022</span>
      </div>
    </div>
  );
}
