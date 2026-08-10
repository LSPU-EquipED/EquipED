// Styled like evaluation/components/Scorecard.tsx's criterion table: same
// column rhythm, same nested evidence box under a row with a quote.
import { cn } from '@/shared/components/utils';
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
      <div className="rounded-sm border border-dashed border-slate-200 bg-slate-50/30 px-4 py-6 text-center text-sm font-semibold text-slate-500">
        No mapped objectives for this course.
      </div>
    );
  }

  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr className="text-left text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
          <th className="px-4 py-2">Objective</th>
          <th className="px-4 py-2">Expected</th>
          <th className="px-4 py-2">Observed</th>
          <th className="px-4 py-2">Status</th>
        </tr>
      </thead>
      <tbody>
        {objectiveResults.map((result) => {
          const normalizedStatus = normalizeBoundedStatus(result.status, coverageScope);
          const downgradeNote = getResultDowngradeNote(result.status, normalizedStatus);

          return (
            <tr key={result.code} className="border-t border-slate-100 align-top">
              <td className="px-4 py-3">
                <div className="text-sm font-semibold text-slate-800">{result.code}</div>
                <div className="text-xs text-slate-500">{result.description}</div>
                {result.evidence ? (
                  <button
                    type="button"
                    onClick={() => {
                      const target = getEvidenceNavigation(result.evidence_page, result.evidence);
                      if (target) {
                        onEvidenceClick?.(target.pageNumber, target.evidence);
                      }
                    }}
                    className="mt-2 block w-full rounded-sm border border-slate-100 bg-slate-50 p-2.5 text-left text-xs font-medium leading-[1.6] text-slate-600 transition-colors hover:bg-slate-100"
                  >
                    &ldquo;{result.evidence}&rdquo;
                  </button>
                ) : null}
                {downgradeNote ? (
                  <p className="mt-2 rounded-sm border border-[#f2c811]/30 bg-[#f2c811]/10 px-2 py-1.5 text-xs font-medium text-[#8a6d00]">
                    {downgradeNote}
                  </p>
                ) : null}
              </td>
              <td className="px-4 py-3 font-bold text-slate-800">{result.expected_level}</td>
              <td className="px-4 py-3 font-bold text-slate-800">{result.observed_level ?? '—'}</td>
              <td className="px-4 py-3">
                <span
                  className={cn(
                    'inline-flex items-center rounded-sm border px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-wider',
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
