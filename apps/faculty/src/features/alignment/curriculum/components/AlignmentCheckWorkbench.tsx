import type { RefObject } from 'react';
import type { AlignmentCheck, DocumentPage } from '../types';
import { AlignmentResultsTable } from './AlignmentResultsTable';
import { SlmReadingPane, type SlmReadingPaneHandle } from './SlmReadingPane';

interface AlignmentCheckWorkbenchProps {
  readingPaneRef: RefObject<SlmReadingPaneHandle>;
  pages: DocumentPage[];
  checkData: AlignmentCheck;
  coverageScope: 'bounded' | 'legacy_unknown' | 'full';
}

export function AlignmentCheckWorkbench({
  readingPaneRef,
  pages,
  checkData,
  coverageScope,
}: AlignmentCheckWorkbenchProps) {
  return (
    <div className="grid auto-rows-[44rem] grid-cols-1 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)] divide-y lg:divide-y-0 lg:divide-x divide-border rounded-md border border-border bg-surface overflow-hidden shadow-none">
      <div className="min-h-0 min-w-0 overflow-hidden flex flex-col">
        <SlmReadingPane
          ref={readingPaneRef}
          pages={pages}
        />
      </div>

      <div className="min-h-0 min-w-0 overflow-hidden flex flex-col bg-surface">
        <div className="flex shrink-0 items-center justify-between border-b border-border bg-surface-subtle/50 px-4 py-2.5">
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-text">
              Mapped Curriculum Objectives
            </h3>
            <p className="text-[11px] text-text-muted">
              Click an evidence quote to scroll the document reader to the source page
            </p>
          </div>
          <span className="text-xs font-mono font-semibold tabular-nums text-text-muted">
            {checkData.objective_results.length} objectives
          </span>
        </div>

        <div
          className="min-h-0 flex-1 overflow-y-auto focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
          role="region"
          aria-label="Mapped curriculum objectives"
          tabIndex={0}
        >
          <AlignmentResultsTable
            objectiveResults={checkData.objective_results}
            coverageScope={coverageScope}
            onEvidenceClick={(pageNumber, evidenceText) =>
              readingPaneRef.current?.scrollToPage(pageNumber, evidenceText)
            }
          />
        </div>
      </div>
    </div>
  );
}
