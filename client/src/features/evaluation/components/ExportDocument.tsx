import { Download } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';

export type ExportAgentId = 'coordinator' | 'sme' | 'gad' | 'itso';

type ExportCriterion = {
  item: string;
  criterion: string;
  rating: '4' | '3' | '2' | '1';
};

type ExportDocument = {
  code: string;
  sectionTitle: string;
  unitName: string;
  filename: string;
  comments: string;
  criteria: readonly ExportCriterion[];
};

const exportDocuments: Record<ExportAgentId, ExportDocument> = {
  coordinator: {
    code: 'LSPU-CID-SF-004',
    sectionTitle: 'A. CURRICULUM ALIGNMENT AND ASSESSMENT',
    unitName: 'PROGRAM COORDINATOR',
    filename: 'LSPU-CID-SF-004-program-coordinator-evaluation-preview.html',
    comments:
      'Assessment evidence should be mapped more directly to syllabus competencies and intended learning outcomes.',
    criteria: [
      {
        item: '1',
        criterion: 'The instructional material is aligned with the approved syllabus coverage.',
        rating: '4',
      },
      {
        item: '2',
        criterion: 'Learning outcomes are clearly stated and connected to module activities.',
        rating: '4',
      },
      {
        item: '3',
        criterion: 'Assessment tasks measure the intended course competencies.',
        rating: '3',
      },
      {
        item: '4',
        criterion: 'Lessons are sequenced according to prerequisite knowledge and course flow.',
        rating: '4',
      },
      {
        item: '5',
        criterion: 'Required references and supporting course materials are complete and appropriate.',
        rating: '3',
      },
    ],
  },
  sme: {
    code: 'LSPU-CID-SF-004',
    sectionTitle: 'A. CONTENT ACCURACY AND INSTRUCTIONAL ORGANIZATION',
    unitName: 'SUBJECT MATTER EXPERT',
    filename: 'LSPU-CID-SF-004-sme-evaluation-preview.html',
    comments: 'Core explanations are accurate. Add one worked example before independent practice.',
    criteria: [
      {
        item: '1',
        criterion: 'The material presents discipline concepts accurately.',
        rating: '4',
      },
      {
        item: '2',
        criterion: 'Examples and explanations are appropriate for the course level.',
        rating: '4',
      },
      {
        item: '3',
        criterion: 'The organization supports self-paced learning and comprehension.',
        rating: '4',
      },
      {
        item: '4',
        criterion: 'Activities reinforce the concepts before learner application.',
        rating: '3',
      },
      {
        item: '5',
        criterion: 'Terminology and references are consistent with the discipline.',
        rating: '4',
      },
    ],
  },
  gad: {
    code: 'LSPU-CID-SF-004',
    sectionTitle: 'A. INCLUSIVITY AND GENDER SENSITIVITY',
    unitName: 'GENDER AND DEVELOPMENT UNIT',
    filename: 'LSPU-CID-SF-004-gad-evaluation-preview.html',
    comments:
      'Review examples for balanced gender representation across roles and scenarios. Replace role-specific assumptions with neutral or inclusive alternatives.',
    criteria: [
      {
        item: '1',
        criterion: 'The material is free from gender stereotypes.',
        rating: '4',
      },
      {
        item: '2',
        criterion: 'The material shows females and males an equal number of times.',
        rating: '3',
      },
      {
        item: '3',
        criterion: 'The material shows females and males with equal respect, and potential.',
        rating: '3',
      },
      {
        item: '4',
        criterion: 'The material reflects the needs and life experiences of both male and female students.',
        rating: '4',
      },
      {
        item: '5',
        criterion:
          'The material promotes peace and equality for males and females, regardless of race, class, disability, religion, sexual preference, or ethnic background.',
        rating: '3',
      },
    ],
  },
  itso: {
    code: 'LSPU-CID-SF-004',
    sectionTitle: 'A. INNOVATION, INTELLECTUAL PROPERTY, AND DATA PRIVACY',
    unitName: 'INNOVATION AND TECHNOLOGY SUPPORT OFFICE',
    filename: 'LSPU-CID-SF-004-itso-evaluation-preview.html',
    comments:
      'Innovation claims are promising, but documentation should better identify originality, ownership, and reuse permissions.',
    criteria: [
      {
        item: '1',
        criterion: 'The material identifies original digital artifacts, tools, or instructional innovations.',
        rating: '4',
      },
      {
        item: '2',
        criterion: 'Third-party materials include ownership, reuse, and attribution details.',
        rating: '3',
      },
      {
        item: '3',
        criterion: 'The material avoids unnecessary exposure of personal or sensitive learner data.',
        rating: '4',
      },
      {
        item: '4',
        criterion: 'Innovation indicators are connected to measurable course deliverables.',
        rating: '3',
      },
      {
        item: '5',
        criterion: 'Digital resources are appropriate, accessible, and compliant with institutional expectations.',
        rating: '4',
      },
    ],
  },
};

function getExportDocument(agentId: ExportAgentId) {
  return exportDocuments[agentId];
}

function getExportTotal(document: ExportDocument) {
  return document.criteria.reduce((total, row) => total + Number(row.rating), 0);
}

function getExportAverage(document: ExportDocument) {
  return getExportTotal(document) / document.criteria.length;
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

function buildExportHtml(agentId: ExportAgentId) {
  const document = getExportDocument(agentId);
  const total = getExportTotal(document);
  const average = getExportAverage(document);
  const adjectivalRating = getAdjectivalRating(average);
  const criteriaRows = document.criteria
    .map(
      (row) => `
        <tr>
          <td class="item">${row.item}</td>
          <td>${row.criterion}</td>
          ${['4', '3', '2', '1']
            .map((rating) => `<td class="rating">${row.rating === rating ? 'x' : ''}</td>`)
            .join('')}
        </tr>`
    )
    .join('');

  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>${document.code} ${document.unitName}</title>
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
      .comments { height: 72px; border: 1px solid #111827; padding: 8px; font-size: 12px; line-height: 1.4; }
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
      <div class="center title">CRITERIA FOR EVALUATION OF INSTRUCTIONAL MATERIALS<br />FOR ${document.unitName}</div>
      <div class="line-grid">
        <div>Name of Faculty: <span class="line">Faculty Reviewer</span></div>
        <div>College: <span class="line">LSPU SCC</span></div>
        <div>Course Title: <span class="line">Outcomes-Based Learning Module</span></div>
        <div>Semester: <span class="line">1st</span></div>
        <div>Academic Year: <span class="line">2025-2026</span></div>
      </div>
      <p class="instruction"><strong>Type of Instructional Material:</strong> [x] Self-paced Learning Module (with OBE Syllabus and Course Guide) &nbsp; [ ] Others: _______________________________</p>
      <p class="instruction"><strong>Instruction:</strong> Rate the materials in the column provided by checking and using the following scale: 4 - Very Satisfactory; 3 - Satisfactory; 2 - Needs Improvement; 1 - Poor</p>
      <table>
        <thead>
          <tr>
            <th colspan="2">${document.sectionTitle}</th>
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
      <div class="comments">${document.comments}</div>
      <div class="signature">
        <div>Signature over Printed Name</div>
        <div>Date Evaluated</div>
      </div>
      <div class="footer">
        <span>${document.code}</span>
        <span>Rev. 0</span>
        <span>23 May 2022</span>
      </div>
    </main>
  </body>
</html>`;
}

function downloadExport(agentId: ExportAgentId) {
  const exportDocument = getExportDocument(agentId);
  const blob = new Blob([buildExportHtml(agentId)], { type: 'text/html;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');

  link.href = url;
  link.download = exportDocument.filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function GadExportDownloadButton({ agentId }: { readonly agentId: ExportAgentId }) {
  return (
    <Button type="button" className="gap-2" onClick={() => downloadExport(agentId)}>
      <Download className="size-4" aria-hidden="true" />
      Download
    </Button>
  );
}

export function GadExportPreview({ agentId }: { readonly agentId: ExportAgentId }) {
  const document = getExportDocument(agentId);
  const total = getExportTotal(document);
  const average = getExportAverage(document);
  const adjectivalRating = getAdjectivalRating(average);

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
        for {document.unitName}
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
          <span className="inline-block min-w-44 border-b border-black">Outcomes-Based Learning Module</span>
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
              {document.sectionTitle}
            </th>
            <th className="w-10 border border-black p-2 text-center">4</th>
            <th className="w-10 border border-black p-2 text-center">3</th>
            <th className="w-10 border border-black p-2 text-center">2</th>
            <th className="w-10 border border-black p-2 text-center">1</th>
          </tr>
        </thead>
        <tbody>
          {document.criteria.map((row) => (
            <tr key={row.item}>
              <td className="w-8 border border-black p-2 text-center">{row.item}</td>
              <td className="border border-black p-2">{row.criterion}</td>
              {['4', '3', '2', '1'].map((rating) => (
                <td key={rating} className="border border-black p-2 text-center font-bold">
                  {row.rating === rating ? 'x' : ''}
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
        <div className="mt-2 min-h-20 border border-black p-2 leading-5">{document.comments}</div>
      </div>

      <div className="mt-12 grid grid-cols-2 gap-20 text-center text-xs">
        <div className="border-t border-black pt-2">Signature over Printed Name</div>
        <div className="border-t border-black pt-2">Date Evaluated</div>
      </div>

      <div className="mt-8 flex justify-between text-[10px]">
        <span>{document.code}</span>
        <span>Rev. 0</span>
        <span>23 May 2022</span>
      </div>
    </div>
  );
}
