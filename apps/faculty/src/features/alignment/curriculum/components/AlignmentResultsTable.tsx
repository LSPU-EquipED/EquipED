// Styled like evaluation/components/Scorecard.tsx's criterion table: same
// column rhythm, same nested evidence box under a row with a quote.
import { cn } from '@equiped/ui';
import { TABLE_STYLES } from '@equiped/ui';
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
      <thead className={cn(TABLE_STYLES.thead, 'sticky top-0 z-10 bg-surface border-b border-border')}>
        <tr>
          <th className={cn(TABLE_STYLES.th, 'w-[55%] min-w-[14rem]')}>Objective</th>
          <th className={cn(TABLE_STYLES.th, 'w-[15%] text-center')}>Expected</th>
          <th className={cn(TABLE_STYLES.th, 'w-[15%] text-center')}>Observed</th>
          <th className={cn(TABLE_STYLES.th, 'w-[15%] text-right')}>Status</th>
        </tr>
      </thead>
      <tbody className={TABLE_STYLES.tbody}>
        {objectiveResults.map((result) => {
          const normalizedStatus = normalizeBoundedStatus(result.status, coverageScope);
          const downgradeNote = getResultDowngradeNote(result.status, normalizedStatus);
          const target = getEvidenceNavigation(result.evidence_page, result.evidence);

          return (
            <tr key={result.code} className="border-t border-border align-top transition-colors hover:bg-surface-subtle/40">
              <td className={TABLE_STYLES.td}>
                <div className="flex items-baseline gap-2">
                  <span className="font-mono text-xs font-bold text-text bg-surface-subtle border border-border px-1.5 py-0.5 rounded-xs">
                    {result.code}
                  </span>
                </div>
                <div className="mt-1 text-xs leading-relaxed text-text-muted">{result.description}</div>
                {result.evidence && target ? (
                  <button
                    type="button"
                    onClick={() => onEvidenceClick?.(target.pageNumber, target.evidence)}
                    className="mt-2.5 block w-full rounded-xs border border-border/80 bg-surface-subtle/50 p-2.5 text-left text-xs font-medium leading-relaxed text-text transition-colors hover:bg-surface hover:border-primary/40 focus-visible:outline-2 focus-visible:outline-ring"
                    title={`Jump to SLM page ${target.pageNumber}`}
                  >
                    <span className="flex items-center justify-between gap-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted mb-1">
                      <span>SLM Evidence (Page {target.pageNumber})</span>
                      <span className="text-primary hover:underline">View in reader →</span>
                    </span>
                    <span className="block italic text-text [overflow-wrap:anywhere]">&ldquo;{result.evidence}&rdquo;</span>
                  </button>
                ) : null}
                {downgradeNote ? (
                  <p className="mt-2 rounded-xs border border-warning/30 bg-warning-soft px-2.5 py-1.5 text-xs font-medium text-warning">
                    {downgradeNote}
                  </p>
                ) : null}
              </td>
              <td className={cn(TABLE_STYLES.tdData, 'text-center')}>
                <span className="font-mono text-xs font-bold text-text tabular-nums">{result.expected_level}</span>
              </td>
              <td className={cn(TABLE_STYLES.tdData, 'text-center')}>
                <span className="font-mono text-xs font-bold text-text tabular-nums">{result.observed_level ?? '—'}</span>
              </td>
              <td className={cn(TABLE_STYLES.td, 'text-right')}>
                <span
                  className={cn(
                    'inline-flex items-center rounded-xs border px-2 py-0.5 text-xs font-semibold tabular-nums select-none',
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
