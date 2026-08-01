import type { EvaluationListItem } from '../types';

/**
 * Pure decision helpers for the confirmed-partial evaluation setup. Kept free
 * of hooks so the confirmation and reuse rules are unit-testable.
 */

export function normalizeProgram(value: string): string {
  return value.trim().toUpperCase();
}

/**
 * The start action stays locked until the faculty user has explicitly
 * confirmed the program (a detected program is only a suggestion) and
 * acknowledged the partial review, and no submission is already pending.
 * This is the no-auto-submit gate: setup never submits on its own.
 */
export function canStartConfirmedPartial({
  program,
  programConfirmed,
  partialAcknowledged,
  isSubmitting,
}: {
  program: string;
  programConfirmed: boolean;
  partialAcknowledged: boolean;
  isSubmitting: boolean;
}): boolean {
  return (
    normalizeProgram(program).length > 0 &&
    programConfirmed &&
    partialAcknowledged &&
    !isSubmitting
  );
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
