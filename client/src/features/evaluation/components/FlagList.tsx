import { Flag, FileText } from 'lucide-react';
import type { EvaluationFlagItem } from '../types';
import type { ClientDocumentChunk } from '@/shared/types/documents';
import { cleanJustification, formatScore } from '../utils/scoreHelpers';

type FlagListProps = {
  readonly flags?: readonly EvaluationFlagItem[];
  readonly agentLabel?: string;
  readonly chunkMap?: ReadonlyMap<string, ClientDocumentChunk>;
};

function scrollToChunk(chunkId: string) {
  const el = document.getElementById(`chunk-${chunkId}`);
  if (!el) return;
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  el.classList.add('bg-[#f2c811]/10');
  window.setTimeout(() => {
    el.classList.remove('bg-[#f2c811]/10');
  }, 1500);
}

export function FlagList({ flags, agentLabel, chunkMap }: FlagListProps) {
  const hasFlags = flags && flags.length > 0;

  return (
    <section className="rounded-sm border border-slate-200 bg-white p-4">
      <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">
        {agentLabel ? `${agentLabel} Flags` : 'Flags'}
      </div>
      <div className="mt-3 grid gap-2">
        {hasFlags ? (
          flags.map((flag) => {
            const linkedChunk = flag.chunk_id && chunkMap ? chunkMap.get(flag.chunk_id) : undefined;
            return (
              <div key={flag.flag_id} className="rounded-md border bg-white p-3">
                <div className="flex items-center gap-2">
                  <Flag className="size-3.5 text-[#f2c811]" aria-hidden="true" />
                  <span className="rounded-full bg-[#f2c811] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[#1e293b]">
                    Score {formatScore(flag.score)}/4
                  </span>
                </div>
                <p className="mt-1.5 text-sm font-medium leading-snug text-slate-900">
                  {flag.criterion_text}
                </p>
                {flag.justification && (
                  <p className="mt-1 text-xs leading-relaxed text-slate-500">
                    {cleanJustification(flag.justification)}
                  </p>
                )}
                {linkedChunk && (
                  <button
                    type="button"
                    onClick={() => scrollToChunk(flag.chunk_id!)}
                    className="mt-2 inline-flex items-center gap-1.5 rounded-md border bg-slate-50/50 px-2 py-1 text-xs font-medium text-slate-500 transition-colors hover:bg-slate-50 hover:text-slate-900"
                  >
                    <FileText className="size-3" aria-hidden="true" />
                    Page {linkedChunk.pageNumber}
                  </button>
                )}
              </div>
            );
          })
        ) : (
          <p className="m-0 rounded-md border bg-white px-3 py-2 text-sm leading-6 text-slate-500">
            Contextual highlights will appear here once evaluation data exists.
          </p>
        )}
      </div>
    </section>
  );
}
