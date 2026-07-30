// Read-only per-page SLM viewer for this feature's own reading pane.
// Deliberately NOT importing evaluation/components/DocumentPane.tsx --
// features must stay self-contained (CLAUDE.md module boundaries) -- so
// the click-to-scroll-and-flash mechanism is reimplemented here, matching
// DocumentPane's exact behavior (scrollIntoView + timed highlight class).
import { forwardRef, useImperativeHandle } from 'react';
import type { DocumentPage } from '../types';

export type SlmReadingPaneHandle = {
  scrollToPage: (pageNumber: number) => void;
};

type SlmReadingPaneProps = {
  pages: DocumentPage[];
};

export const SlmReadingPane = forwardRef<SlmReadingPaneHandle, SlmReadingPaneProps>(
  function SlmReadingPane({ pages }, ref) {
    useImperativeHandle(ref, () => ({
      scrollToPage: (pageNumber: number) => {
        setTimeout(() => {
          const el = window.document.getElementById(`page-${pageNumber}`);
          if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            el.classList.add('bg-[#f2c811]/15');
            setTimeout(() => {
              el.classList.remove('bg-[#f2c811]/15');
            }, 1500);
          }
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

    return (
      <div className="h-full overflow-y-auto bg-[#f8fafc] p-4">
        {pages.map((page) => (
          <div
            key={page.page_number}
            id={`page-${page.page_number}`}
            className="mb-3 rounded-sm border border-slate-200 bg-white p-4 transition-colors"
          >
            <div className="mb-2 text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
              Page {page.page_number}
            </div>
            <div className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
              {page.text}
            </div>
          </div>
        ))}
      </div>
    );
  },
);
