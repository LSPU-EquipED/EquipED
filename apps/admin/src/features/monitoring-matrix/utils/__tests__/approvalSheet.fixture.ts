import type { MasterSynthesisDetailResponse } from '../../types';

export function approvalSheetData(): MasterSynthesisDetailResponse {
  return {
    document_id: 'private-document-id', document_title: 'Module title is not the course title',
    course_code: 'CS101', course_title: 'Human-computer interaction', academic_year: '2026-2027',
    program: 'BSCS', author: { user_id: 'author-id', name: 'Maria Santos', email: 'private@lspu.edu.ph', department: 'CCS' },
    synthesized_score: 79, adjectival_rating: 'Satisfactory', evaluation_status: 'COMPLETED',
    last_updated: '2026-10-07T10:00:00Z', flags: [], can_certify: true,
    pillars: Object.fromEntries(['sme', 'coordinator', 'gad', 'itso'].map((agent, index) => [agent, {
      weight: 0.25, subtotal: 3, status: 'COMPLETED', criteria: [], summary: 'Private advisory summary',
      evaluator: { user_id: `${agent}-id`, name: ['Ana Reyes', 'Jose Cruz', 'Maria Garcia', 'Pedro Santos'][index], email: 'private@lspu.edu.ph', department: 'CCS' },
    }])),
  };
}
