// Styled like evaluation/components/Scorecard.tsx's criterion table: same
// column rhythm, same nested evidence box under a row with a quote.
import { cn } from '@/shared/components/utils';
import { TABLE_STYLES } from '@/shared/constants/theme';
import { statusBadgeClasses, statusLabel } from '../utils/alignmentHelpers';
import {
  getEvidenceNavigation,
  getResultDowngradeNote,
  normalizeBoundedStatus,
} from '../utils/alignmentState';
import type { ObjectiveResult } from '../types';
import type { AlignmentCoverageScope } from '../types';

type AlignmentResultsTableProps = {
  objectiveResults: ObjectiveResult[];
  coverageScope?: AlignmentCoverageScope;
  onEvidenceClick?: (pageNumber: number, evidence?: string | null) => void;
};

export function AlignmentResultsTable({
  objectiveResults,
  coverageScope = 'legacy_unknown',
  onEvidenceClick,
}: AlignmentResultsTableProps) {
  if (objectiveResults.length === 0) {
    return (
      <div className="rounded-sm border border-dashed border-border bg-surface-subtle/50 px-4 py-6 text-center text-sm font-semibold text-text-muted">
        No mapped objectives for this course.
      </div>
    );
  }

  return (
    <table className={TABLE_STYLES.table}>
      <thead className={TABLE_STYLES.thead}>
        <tr>
          <th className={TABLE_STYLES.th}>Objective</th>
          <th className={TABLE_STYLES.th}>Expected</th>
          <th className={TABLE_STYLES.th}>Observed</th>
          <th className={TABLE_STYLES.th}>Status</th>
        </tr>
      </thead>
      <tbody className={TABLE_STYLES.tbody}>
        {objectiveResults.map((result) => {
          const normalizedStatus = normalizeBoundedStatus(result.status, coverageScope);
          const downgradeNote = getResultDowngradeNote(result.status, normalizedStatus);

          return (
            <tr key={result.code} className="border-t border-border align-top transition-colors hover:bg-surface-subtle/50">
              <td className={TABLE_STYLES.td}>
                <div className="text-sm font-semibold text-text">{result.code}</div>
                <div className="text-xs text-text-muted">{result.description}</div>
                {result.evidence ? (
                  <button
                    type="button"
                    onClick={() => {
                      const target = getEvidenceNavigation(result.evidence_page, result.evidence);
                      if (target) {
                        onEvidenceClick?.(target.pageNumber, target.evidence);
                      }
                    }}
                    className="mt-2 block w-full rounded-sm border border-border bg-surface-subtle p-2.5 text-left text-xs font-medium leading-[1.6] text-text transition-colors hover:bg-surface hover:border-border"
                  >
                    &ldquo;{result.evidence}&rdquo;
                  </button>
                ) : null}
                {downgradeNote ? (
                  <p className="mt-2 rounded-sm border border-warning/30 bg-warning-soft px-2 py-1.5 text-xs font-medium text-warning">
                    {downgradeNote}
                  </p>
                ) : null}
              </td>
              <td className={cn(TABLE_STYLES.tdData, 'font-bold')}>{result.expected_level}</td>
              <td className={cn(TABLE_STYLES.tdData, 'font-bold')}>{result.observed_level ?? '—'}</td>
              <td className={TABLE_STYLES.td}>
                <span
                  className={cn(
                    'inline-flex items-center rounded-xs border px-2 py-0.5 text-xs font-semibold tracking-wide select-none',
                    statusBadgeClasses(normalizedStatus),
                  )}
                >
                  {statusLabel(normalizedStatus)}
                </span>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
