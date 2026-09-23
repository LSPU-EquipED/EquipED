import type { StatusVariant } from '../theme';

/**
 * Pure shared presentation mapping for evaluation lifecycle and execution statuses.
 * Maps evaluation status strings to design system Badge StatusVariant tokens.
 *
 * Evaluation lifecycle:
 * SUBMITTED -> PREPROCESSING -> EVALUATING -> SYNTHESIZING -> COMPLETED | FAILED | COMPLETED_PARTIAL
 *
 * Evaluation statuses and their variants:
 * - FAILED, ERROR -> 'destructive'
 * - COMPLETED_PARTIAL -> 'warning' (aligned with Faculty presentation of partial results)
 * - COMPLETED, COMPLETED_WITH_WARNINGS (or other completed variants) -> 'success'
 * - IN_PROGRESS, IN PROGRESS, EVALUATING, PREPROCESSING, SYNTHESIZING, PROCESSING -> 'info'
 * - SUBMITTED, PENDING, QUEUED, REVISION (or revision states) -> 'warning'
 * - All other / unknown / null / empty -> 'neutral'
 */
export function getEvaluationStatusVariant(status?: string | null): StatusVariant {
  if (!status) return 'neutral';
  const s = status.trim().toUpperCase();

  if (s === 'FAILED' || s === 'ERROR') return 'destructive';
  if (s === 'COMPLETED_PARTIAL') return 'warning';
  if (s.startsWith('COMPLETED')) return 'success';
  if (
    s === 'IN_PROGRESS' ||
    s === 'IN PROGRESS' ||
    s === 'EVALUATING' ||
    s === 'PREPROCESSING' ||
    s === 'SYNTHESIZING' ||
    s === 'PROCESSING'
  ) {
    return 'info';
  }
  if (
    s === 'SUBMITTED' ||
    s === 'PENDING' ||
    s === 'QUEUED' ||
    s.includes('REVISION')
  ) {
    return 'warning';
  }

  return 'neutral';
}
