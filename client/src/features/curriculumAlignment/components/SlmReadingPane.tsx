// client/src/features/curriculumAlignment/components/SlmReadingPane.tsx
// Read-only per-page SLM viewer for this feature's own reading pane.
// Deliberately NOT importing evaluation/components/DocumentPane.tsx --
// features must stay self-contained (CLAUDE.md module boundaries) -- so
// the pager (prev/next + page dropdown, one page shown at a time) and the
// click-to-scroll-and-flash mechanism are reimplemented here, matching
// DocumentPane's exact behavior.
import { forwardRef, useEffect, useImperativeHandle, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { DocumentPage } from '../types';

export type SlmReadingPaneHandle = {
  scrollToPage: (pageNumber: number) => void;
};

type SlmReadingPaneProps = {
  pages: DocumentPage[];
};

export const SlmReadingPane = forwardRef<SlmReadingPaneHandle, SlmReadingPaneProps>(
  function SlmReadingPane({ pages }, ref) {
    const [currentPage, setCurrentPage] = useState<number>(pages[0]?.page_number ?? 1);
    const [flashed, setFlashed] = useState(false);

    useEffect(() => {
      if (pages.length > 0 && !pages.some((p) => p.page_number === currentPage)) {
        setCurrentPage(pages[0].page_number);
      }
    }, [pages, currentPage]);

    useImperativeHandle(ref, () => ({
      scrollToPage: (pageNumber: number) => {
        setCurrentPage(pageNumber);
        setTimeout(() => {
          setFlashed(true);
          setTimeout(() => setFlashed(false), 1500);
        }, 150);
      },
    }));

    if (pages.length === 0) {
      return (
        <div className="flex h-full items-center justify-center text-sm font-semibold text-slate-500">
          No document content available.
        </div>
      );
    }

    const currentIndex = pages.findIndex((p) => p.page_number === currentPage);
    const activePage = pages[currentIndex] ?? pages[0];

    const handlePrevPage = () => {
      if (currentIndex > 0) setCurrentPage(pages[currentIndex - 1].page_number);
    };

    const handleNextPage = () => {
      if (currentIndex >= 0 && currentIndex < pages.length - 1) {
        setCurrentPage(pages[currentIndex + 1].page_number);
      }
    };

    return (
      <div className="flex h-full flex-col bg-[#f8fafc]">
        <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-2">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
            SLM Content
          </span>
          <div className="flex items-center border border-slate-200 rounded-sm bg-white p-0.5">
            <button
              type="button"
              onClick={handlePrevPage}
              disabled={currentIndex <= 0}
              className="inline-flex size-7 items-center justify-center text-slate-500 hover:bg-slate-50 hover:text-slate-950 disabled:opacity-30 disabled:hover:bg-transparent transition-colors cursor-pointer"
              aria-label="Previous page"
            >
              <ChevronLeft className="size-4" />
            </button>
            <div className="px-2">
              <select
                value={currentPage}
                onChange={(e) => setCurrentPage(Number(e.target.value))}
                className="bg-transparent text-xs font-semibold text-slate-700 outline-none cursor-pointer focus:ring-0 border-0 p-0"
              >
                {pages.map((page, idx) => (
                  <option key={page.page_number} value={page.page_number}>
                    Page {idx + 1} of {pages.length}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              onClick={handleNextPage}
              disabled={currentIndex < 0 || currentIndex >= pages.length - 1}
              className="inline-flex size-7 items-center justify-center text-slate-500 hover:bg-slate-50 hover:text-slate-950 disabled:opacity-30 disabled:hover:bg-transparent transition-colors cursor-pointer"
              aria-label="Next page"
            >
              <ChevronRight className="size-4" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          <div
            className={`rounded-sm border border-slate-200 bg-white p-4 transition-colors ${
              flashed ? 'bg-[#f2c811]/15' : ''
            }`}
          >
            <div className="mb-2 text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
              Page {activePage.page_number}
            </div>
            <div className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
              {activePage.text}
            </div>
          </div>
        </div>
      </div>
    );
  },
);
