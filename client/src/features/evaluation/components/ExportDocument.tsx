import { Download } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import type { DomainScoreBlock } from '../types';

export type ExportDomainData = DomainScoreBlock & {
  agentId: string;
  documentTitle?: string;
  program?: string;
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

function buildExportHtml(domainData: ExportDomainData) {
  const config = AGENT_CONFIGS[domainData.agentId] || { 
    code: 'N/A', 
    sectionTitle: 'EVALUATION CRITERIA', 
    unitName: domainData.agentId.toUpperCase() 
  };
  const total = getExportTotal(domainData);
  const average = getExportAverage(domainData);
  const adjectivalRating = getAdjectivalRating(average);
  
  const criteriaRows = domainData.criteria
    .map(
      (row, idx) => `
        <tr>
          <td class="item">${idx + 1}</td>
          <td>${row.criterion_text}</td>
          ${['4', '3', '2', '1']
            .map((rating) => `<td class="rating">${row.score.toString() === rating ? 'x' : ''}</td>`)
            .join('')}
        </tr>`
    )
    .join('');

  const comments = domainData.criteria
    .filter(c => c.justification)
    .map(c => c.justification)
    .join('\n\n');

  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>${config.code} ${config.unitName}</title>
    <style>
      body { margin: 0; background: #f4f4f5; color: #111827; font-family: Arial, sans-serif; }
      .page { width: 8.5in; min-height: 11in; margin: 24px auto; background: white; padding: 0.45in; box-sizing: border-box; }
      .center { text-align: center; }
      .small { font-size: 11px; }
      .title { margin: 18px 0 14px; font-size: 15px; font-weight: 700; letter-spacing: 0.04em; }
      .line-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 18px; font-size: 12px; }
      .line { border-bottom: 1px solid #111827; min-height: 18px; display: inline-block; min-width: 160px; }
      .instruction { margin-top: 14px; font-size: 12px; line-height: 1.4; }
      table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 11px; }
      th, td { border: 1px solid #111827; padding: 6px; vertical-align: top; }
      th { text-align: center; font-weight: 700; }
      .item { width: 28px; text-align: center; }
      .rating { width: 36px; text-align: center; font-weight: 700; }
      .footer { display: flex; justify-content: space-between; margin-top: 26px; font-size: 10px; }
      .signature { display: grid; grid-template-columns: 1fr 1fr; gap: 70px; margin-top: 38px; text-align: center; font-size: 12px; }
      .signature div { border-top: 1px solid #111827; padding-top: 6px; }
      .comments { min-height: 72px; border: 1px solid #111827; padding: 8px; font-size: 12px; line-height: 1.4; white-space: pre-wrap; }
      @media print {
        body { background: white; }
        .page { margin: 0; box-shadow: none; }
      }
    </style>
  </head>
  <body>
    <main class="page">
      <div class="center small">
        <div>Republic of the Philippines</div>
        <div><strong>Laguna State Polytechnic University</strong></div>
        <div>Province of Laguna</div>
      </div>
      <div class="center title">CRITERIA FOR EVALUATION OF INSTRUCTIONAL MATERIALS<br />FOR ${config.unitName}</div>
      <div class="line-grid">
        <div>Name of Faculty: <span class="line">Faculty Reviewer</span></div>
        <div>College: <span class="line">LSPU SCC</span></div>
        <div>Course Title: <span class="line">${domainData.documentTitle || 'Outcomes-Based Learning Module'}</span></div>
        <div>Semester: <span class="line">1st</span></div>
        <div>Academic Year: <span class="line">2025-2026</span></div>
      </div>
      <p class="instruction"><strong>Type of Instructional Material:</strong> [x] Self-paced Learning Module (with OBE Syllabus and Course Guide) &nbsp; [ ] Others: _______________________________</p>
      <p class="instruction"><strong>Instruction:</strong> Rate the materials in the column provided by checking and using the following scale: 4 - Very Satisfactory; 3 - Satisfactory; 2 - Needs Improvement; 1 - Poor</p>
      <table>
        <thead>
          <tr>
            <th colspan="2">${config.sectionTitle}</th>
            <th>4</th>
            <th>3</th>
            <th>2</th>
            <th>1</th>
          </tr>
        </thead>
        <tbody>${criteriaRows}</tbody>
      </table>
      <p class="instruction"><strong>Total:</strong> ${total} &nbsp;&nbsp; <strong>Total Score/5:</strong> ${average.toFixed(2)} &nbsp;&nbsp; <strong>Adjectival Rating:</strong> ${adjectivalRating}</p>
      <p class="instruction">3.50 - 4.00 = Very Satisfactory &nbsp; 2.50 - 3.49 = Satisfactory &nbsp; 1.50 - 2.49 = Needs Improvement &nbsp; 1.00 - 1.49 = Poor</p>
      <p class="instruction"><strong>Additional Comments/Suggestions:</strong></p>
      <div class="comments">${comments}</div>
      <div class="signature">
        <div>Signature over Printed Name</div>
        <div>Date Evaluated</div>
      </div>
      <div class="footer">
        <span>${config.code}</span>
        <span>Rev. 0</span>
        <span>23 May 2022</span>
      </div>
    </main>
  </body>
</html>`;
}

function downloadExport(domainData: ExportDomainData) {
  const config = AGENT_CONFIGS[domainData.agentId] || { code: 'N/A' };
  const filename = `${config.code}-${domainData.agentId}-evaluation-preview.html`;
  const blob = new Blob([buildExportHtml(domainData)], { type: 'text/html;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');

  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function GadExportDownloadButton({ domainData }: { readonly domainData: ExportDomainData }) {
  return (
    <Button type="button" className="gap-2" onClick={() => downloadExport(domainData)}>
      <Download className="size-4" aria-hidden="true" />
      Download
    </Button>
  );
}

export function GadExportPreview({ domainData }: { readonly domainData: ExportDomainData }) {
  const config = AGENT_CONFIGS[domainData.agentId] || { 
    code: 'N/A', 
    sectionTitle: 'EVALUATION CRITERIA', 
    unitName: domainData.agentId.toUpperCase() 
  };
  const total = getExportTotal(domainData);
  const average = getExportAverage(domainData);
  const adjectivalRating = getAdjectivalRating(average);

  const comments = domainData.criteria
    .filter(c => c.justification)
    .map(c => c.justification)
    .join('\n\n');

  return (
    <div className="mx-auto min-h-[11in] w-[8.5in] resize overflow-auto bg-white p-12 text-[11px] text-black shadow-sm">
      <div className="text-center leading-5">
        <div>Republic of the Philippines</div>
        <div className="font-semibold">Laguna State Polytechnic University</div>
        <div>Province of Laguna</div>
      </div>

      <h2 className="mt-5 text-center text-sm font-bold uppercase tracking-wide">
        Criteria for Evaluation of Instructional Materials
        <br />
        for {config.unitName}
      </h2>

      <div className="mt-5 grid grid-cols-2 gap-x-8 gap-y-2 text-xs">
        <div>
          Name of Faculty: <span className="inline-block min-w-44 border-b border-black">Faculty Reviewer</span>
        </div>
        <div>
          College: <span className="inline-block min-w-32 border-b border-black">LSPU SCC</span>
        </div>
        <div>
          Course Title:{' '}
          <span className="inline-block min-w-44 border-b border-black">{domainData.documentTitle || 'Outcomes-Based Learning Module'}</span>
        </div>
        <div>
          Semester: <span className="inline-block min-w-24 border-b border-black">1st</span>
        </div>
        <div>
          Academic Year: <span className="inline-block min-w-28 border-b border-black">2025-2026</span>
        </div>
      </div>

      <div className="mt-4 text-xs leading-5">
        <div>
          <strong>Type of Instructional Material:</strong> [x] Self-paced Learning Module (with OBE Syllabus and
          Course Guide)
        </div>
        <div>[ ] Others (Please specify): ____________________________________________</div>
      </div>

      <p className="mt-4 text-xs leading-5">
        <strong>Instruction:</strong> Rate the materials in the column provided by checking and using the following
        scale: 4 - Very Satisfactory; 3 - Satisfactory; 2 - Needs Improvement; 1 - Poor
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
        3.50 - 4.00 = Very Satisfactory; 2.50 - 3.49 = Satisfactory; 1.50 - 2.49 = Needs Improvement; 1.00 - 1.49 =
        Poor
      </p>

      <div className="mt-4 text-xs">
        <strong>Additional Comments/Suggestions:</strong>
        <div className="mt-2 min-h-20 border border-black p-2 leading-5 whitespace-pre-wrap">{comments}</div>
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
