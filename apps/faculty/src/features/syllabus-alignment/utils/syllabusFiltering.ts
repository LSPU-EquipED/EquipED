import type { AlignmentSlmItem, AlignmentSlmStats } from '../types';

export type StatusFilter = 'ALL' | 'MEETS' | 'PARTIALLY_MEETS' | 'ATTENTION' | 'PENDING';

export interface SyllabusAlignmentMetrics {
  meets: number;
  partiallyMeets: number;
  attention: number;
  pending: number;
}

export function deriveSyllabusMetrics(
  stats?: AlignmentSlmStats,
  items: AlignmentSlmItem[] = [],
): SyllabusAlignmentMetrics {
  if (stats) {
    return {
      meets: stats.meets,
      partiallyMeets: stats.partially_meets,
      attention: stats.needs_attention,
      pending: stats.pending,
    };
  }
  const meets = items.filter((item) => item.current_result?.alignment_level === 'MEETS').length;
  const partiallyMeets = items.filter(
    (item) => item.current_result?.alignment_level === 'PARTIALLY_MEETS',
  ).length;
  const attention = items.filter(
    (item) =>
      item.current_result?.alignment_level === 'DOES_NOT_MEET' ||
      item.current_result?.status === 'FAILED',
  ).length;
  const pending = items.filter(
    (item) =>
      !item.current_result ||
      ['QUEUED', 'RUNNING'].includes(item.current_result?.status ?? ''),
  ).length;
  return { meets, partiallyMeets, attention, pending };
}

export function filterSyllabusItems(
  items: AlignmentSlmItem[],
  statusFilter: StatusFilter,
  search: string,
): AlignmentSlmItem[] {
  const query = search.trim().toLowerCase();

  return items.filter((item) => {
    // Status filter
    if (statusFilter === 'MEETS' && item.current_result?.alignment_level !== 'MEETS') {
      return false;
    }
    if (
      statusFilter === 'PARTIALLY_MEETS' &&
      item.current_result?.alignment_level !== 'PARTIALLY_MEETS'
    ) {
      return false;
    }
    if (statusFilter === 'ATTENTION') {
      const isAttention =
        item.current_result?.alignment_level === 'DOES_NOT_MEET' ||
        item.current_result?.status === 'FAILED';
      if (!isAttention) return false;
    }
    if (statusFilter === 'PENDING') {
      const isPending =
        !item.current_result ||
        ['QUEUED', 'RUNNING'].includes(item.current_result?.status ?? '');
      if (!isPending) return false;
    }

    // Search query filter
    if (!query) return true;
    return (
      item.title.toLowerCase().includes(query) ||
      (item.course_title && item.course_title.toLowerCase().includes(query)) ||
      (item.lesson_title && item.lesson_title.toLowerCase().includes(query)) ||
      (item.program && item.program.toLowerCase().includes(query)) ||
      (item.current_result?.syllabus_title &&
        item.current_result.syllabus_title.toLowerCase().includes(query))
    );
  });
}
