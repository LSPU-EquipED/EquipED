// Read-only per-page SLM viewer for this feature's own reading pane.
// Deliberately NOT importing evaluation/components/DocumentPane.tsx --
// features must stay self-contained (CLAUDE.md module boundaries) -- so
// the pager (prev/next + page dropdown, one page shown at a time) and the
// click-to-scroll-and-flash mechanism are reimplemented here, matching
// DocumentPane's exact behavior.
import { forwardRef, useEffect, useImperativeHandle, useState } from 'react';
import { CaretLeft, CaretRight } from '@phosphor-icons/react';
import type { DocumentPage } from '../types';

export type SlmReadingPaneHandle = {
  scrollToPage: (pageNumber: number, evidenceText?: string | null) => void;
};

type Match = {
  before: string;
  match: string;
  after: string;
};

type SlmReadingPaneProps = {
  pages: DocumentPage[];
};

function findEvidenceMatchIndex(text: string, evidenceText: string): Match | null {
  if (!evidenceText) {
    return null;
  }

  const normalizedText = text;
  const normalizedEvidence = evidenceText.trim();
  const idx = normalizedText.toLowerCase().indexOf(normalizedEvidence.toLowerCase());

  if (idx === -1) {
    return null;
  }

  return {
    before: text.slice(0, idx),
    match: text.slice(idx, idx + normalizedEvidence.length),
    after: text.slice(idx + normalizedEvidence.length),
  };
}

export const SlmReadingPane = forwardRef<SlmReadingPaneHandle, SlmReadingPaneProps>(
  function SlmReadingPane({ pages }, ref) {
    const [currentPage, setCurrentPage] = useState<number>(pages[0]?.page_number ?? 1);
    const [highlight, setHighlight] = useState<string>('');
    const [highlighted, setHighlighted] = useState(false);
    const [flashed, setFlashed] = useState(false);

    useEffect(() => {
      if (pages.length > 0 && !pages.some((p) => p.page_number === currentPage)) {
        setCurrentPage(pages[0].page_number);
      }
    }, [pages, currentPage]);

    useImperativeHandle(ref, () => ({
      scrollToPage: (pageNumber: number, evidenceText?: string | null) => {
        const hasPage = pages.some((page) => page.page_number === pageNumber);
        if (!hasPage) {
          return;
        }

        setCurrentPage(pageNumber);
        setHighlight(evidenceText?.trim() ?? '');

        setTimeout(() => {
          setFlashed(true);
          setTimeout(() => setFlashed(false), 1200);
        }, 120);

        if (!evidenceText) {
          return;
        }

        setHighlighted(true);
        setTimeout(() => setHighlighted(false), 1200);
      },
    }));

    if (pages.length === 0) {
      return (
        <div className="flex h-full items-center justify-center text-sm font-semibold text-text-muted">
          No document content available.
        </div>
      );
    }

    const currentIndex = pages.findIndex((p) => p.page_number === currentPage);
    const activePage = pages[currentIndex] ?? pages[0];
    const match =
      currentIndex >= 0 && highlighted
        ? findEvidenceMatchIndex(activePage.text, highlight)
        : null;

    const handlePrevPage = () => {
      if (currentIndex > 0) setCurrentPage(pages[currentIndex - 1].page_number);
    };

    const handleNextPage = () => {
      if (currentIndex >= 0 && currentIndex < pages.length - 1) {
        setCurrentPage(pages[currentIndex + 1].page_number);
      }
    };

    return (
      <div className="flex h-full flex-col bg-canvas">
        <div className="flex h-11 items-center justify-between border-b border-border bg-surface px-4">
          <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">
            SLM Document Reader
          </span>

          <div className="flex items-center gap-1 rounded-xs border border-border bg-surface-subtle/60 p-0.5">
            <button
              type="button"
              onClick={handlePrevPage}
              disabled={currentIndex <= 0}
              className="inline-flex size-6.5 items-center justify-center rounded-xs text-text-muted hover:bg-surface hover:text-text disabled:opacity-30 disabled:hover:bg-transparent transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-ring"
              aria-label="Previous page"
              title="Previous page"
            >
              <CaretLeft className="size-3.5" />
            </button>
            <span className="px-2 text-xs font-semibold tabular-nums text-text-muted">
              Page {activePage.page_number} of {pages.length}
            </span>
            <button
              type="button"
              onClick={handleNextPage}
              disabled={currentIndex < 0 || currentIndex >= pages.length - 1}
              className="inline-flex size-6.5 items-center justify-center rounded-xs text-text-muted hover:bg-surface hover:text-text disabled:opacity-30 disabled:hover:bg-transparent transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-ring"
              aria-label="Next page"
              title="Next page"
            >
              <CaretRight className="size-3.5" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 sm:p-5">
          <article
            className={`min-h-[32rem] rounded-sm border border-border bg-surface p-6 sm:p-8 transition-colors ${
              flashed ? 'bg-warning-soft/30 ring-1 ring-warning/50' : ''
            }`}
          >
            <header className="mb-4 pb-2 border-b border-border/60 flex items-center justify-between text-xs text-text-muted">
              <span className="font-semibold uppercase tracking-wider text-[10px]">
                SLM Content — Page {activePage.page_number}
              </span>
              <span className="text-[11px] tabular-nums">
                {activePage.text.length} characters
              </span>
            </header>
            <div className="whitespace-pre-wrap text-sm leading-[1.75] text-text font-normal [overflow-wrap:anywhere]">
              {match ? (
                <>
                  {match.before}
                  <mark className="rounded-xs bg-warning-soft text-warning font-semibold px-1 py-0.5 border border-warning/40">
                    {match.match}
                  </mark>
                  {match.after}
                </>
              ) : (
                activePage.text
              )}
            </div>
          </article>
        </div>
      </div>
    );
  },
);
