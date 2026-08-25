import { isLspuSccProgram, normalizeProgram } from '@/shared/constants/programs';
import type { EvaluationListItem, EvaluationSubmitRequest } from '../types';

/**
 * Pure decision helpers for evaluation setup (Full and Partial modes). Kept free
 * of hooks so the confirmation, mode selection, and payload generation rules are unit-testable.
 */

export type EvaluationMode = 'full' | 'partial';

export { normalizeProgram };

export interface CanStartEvaluationParams {
  program: string;
  programConfirmed: boolean;
  mode: EvaluationMode | null;
  selectedCurriculumId?: string | null;
  readyCurriculumIds?: string[];
  partialAcknowledged?: boolean;
  isLoadingCurricula?: boolean;
  isCurriculaError?: boolean;
  isResolveError?: boolean;
  isSubmitting: boolean;
}

/**
 * The start action stays locked until the faculty user has explicitly
 * confirmed the program (a detected program is only a suggestion), chosen
 * a valid evaluation mode, and satisfied that mode's explicit prerequisites.
 *
 * Full Evaluation requires:
 * - existing evaluation resolver succeeded (no resolver failure)
 * - supported and confirmed program (e.g. BSCS, BSInfoTech)
 * - explicit selection of a currently ready curriculum (no auto-selection)
 * - curriculum suggestions not currently loading or in error
 * - no active submission in progress
 *
 * Partial Evaluation requires:
 * - existing evaluation resolver succeeded (no resolver failure)
 * - supported and confirmed program (e.g. BSCS, BSInfoTech)
 * - explicit acknowledgement of partial review terms (no coordinator)
 * - no active submission in progress
 */
export function canStartEvaluation({
  program,
  programConfirmed,
  mode,
  selectedCurriculumId,
  readyCurriculumIds,
  partialAcknowledged,
  isLoadingCurricula = false,
  isCurriculaError = false,
  isResolveError = false,
  isSubmitting,
}: CanStartEvaluationParams): boolean {
  if (isSubmitting || isResolveError) return false;
  if (!program || !isLspuSccProgram(program) || !programConfirmed) {
    return false;
  }

  if (mode === 'full') {
    if (isLoadingCurricula || isCurriculaError) return false;
    if (!selectedCurriculumId || selectedCurriculumId.trim().length === 0) return false;
    if (readyCurriculumIds && !readyCurriculumIds.includes(selectedCurriculumId.trim())) {
      return false;
    }
    return true;
  }

  if (mode === 'partial') {
    return Boolean(partialAcknowledged);
  }

  return false;
}

/**
 * Builds the exact typed submission payload for full or partial evaluation.
 * Enforces supported-program writes and normalizes alias reads to canonical constants (BSInfoTech, BSCS).
 */
export function buildEvaluationSubmitPayload({
  documentId,
  program,
  mode,
  curriculumId,
}: {
  documentId: string;
  program: string;
  mode: EvaluationMode;
  curriculumId?: string | null;
}): EvaluationSubmitRequest {
  if (!program || !isLspuSccProgram(program)) {
    throw new Error(
      `Invalid program '${program}'. Must be a supported LSPU SCC program ('BSCS' or 'BSInfoTech').`,
    );
  }

  const confirmed_program = normalizeProgram(program);

  if (mode === 'full') {
    if (!curriculumId || curriculumId.trim().length === 0) {
      throw new Error('Curriculum ID is required for full evaluation');
    }
    return {
      document_id: documentId,
      curriculum_id: curriculumId.trim(),
      confirmed_program,
      partial_without_curriculum: false,
    };
  }

  return {
    document_id: documentId,
    confirmed_program,
    partial_without_curriculum: true,
  };
}

/**
 * Reuse an existing evaluation for the SLM: the most recent non-failed job
 * wins. When only failed jobs exist (or none), the user returns to setup.
 */
export function resolveExistingEvaluation(
  items: Pick<EvaluationListItem, 'evaluation_id' | 'status' | 'submitted_at'>[],
): string | null {
  const nonFailed = items
    .filter((item) => item.status !== 'FAILED')
    .sort(
      (left, right) =>
        new Date(right.submitted_at).getTime() - new Date(left.submitted_at).getTime(),
    );

  return nonFailed.length > 0 ? nonFailed[0].evaluation_id : null;
}
