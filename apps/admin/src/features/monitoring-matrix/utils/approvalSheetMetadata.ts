import { LSPU_SCC_COLLEGE_PROGRAMS, normalizeProgram } from '@equiped/types';
import type { MasterSynthesisDetailResponse } from '../types';
import { TARGET_DOMAIN_ORDER } from './matrixFormatters';
import { APPROVAL_SHEET_SIGNATORIES } from './approvalSheetSignatories';

/** Names come from the selected synthesis record, never the exporting admin. */
function recordedName(name: string | null | undefined): string {
  const value = name?.trim() || '';
  return /^unknown (author|evaluator)$/i.test(value) ? '' : value;
}

export function approvalSheetMetadata(data: MasterSynthesisDetailResponse) {
  const program = normalizeProgram(data.program || '');
  const college = LSPU_SCC_COLLEGE_PROGRAMS.find((group) =>
    group.programs.some((entry) => entry.code === program),
  );
  const reviewers = Object.fromEntries(TARGET_DOMAIN_ORDER.map((agent) => {
    const pillar = data.pillars[agent];
    const completed = pillar && ['OK', 'COMPLETED'].includes(pillar.status.toUpperCase())
      && pillar.subtotal !== null && Number.isFinite(pillar.subtotal)
      && pillar.subtotal >= 0 && pillar.subtotal <= 4;
    return [agent, completed
      ? recordedName(pillar.evaluator?.name).toUpperCase() : ''];
  }));
  return {
    materialType: 'Self-paced Learning Module (SLM)',
    courseTitle: data.course_title || '',
    // Intentionally leave Author/s for manual completion.
    authors: '',
    campus: 'Santa Cruz Campus',
    college: college?.college || '',
    academicYear: data.academic_year || '',
    // Semester and institutional approval/signature data are not persisted.
    semester: '',
    reviewers,
    signatories: {
      dean: (college ? APPROVAL_SHEET_SIGNATORIES.deansByCollege[college.code] || '' : '').toUpperCase(),
      chairperson: APPROVAL_SHEET_SIGNATORIES.chairperson.toUpperCase(),
      director: APPROVAL_SHEET_SIGNATORIES.director.toUpperCase(),
      vicePresident: APPROVAL_SHEET_SIGNATORIES.vicePresident.toUpperCase(),
    },
  };
}
