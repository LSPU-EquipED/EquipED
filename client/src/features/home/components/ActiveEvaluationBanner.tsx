import { Link } from '@tanstack/react-router';
import { ArrowRight, Loader2, PlayCircle } from 'lucide-react';
import type { FacultyHomeData } from '../types';
import { formatDateTime } from '../utils/homeData';

interface ActiveEvaluationBannerProps {
  homeData: FacultyHomeData;
}

export function ActiveEvaluationBanner({ homeData }: ActiveEvaluationBannerProps) {
  const { activeEvaluation, latestReadyDocument } = homeData;

  if (activeEvaluation) {
    return (
      <div className="rounded-sm border border-[#1b3b87]/30 bg-slate-50 p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-start gap-3.5">
          <div className="flex size-10 items-center justify-center rounded-sm border border-[#1b3b87]/30 bg-[#1b3b87]/10 text-[#1b3b87] shrink-0 mt-0.5">
            <Loader2 className="size-5 animate-spin" aria-hidden="true" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center rounded-sm bg-[#1b3b87] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">
                Active Evaluation
              </span>
              <span className="text-xs text-slate-500 font-medium">
                Submitted {formatDateTime(activeEvaluation.submitted_at)}
              </span>
            </div>
            <h3 className="mt-1 text-base font-bold text-slate-900">
              {activeEvaluation.document_title || 'Untitled SLM'}
            </h3>
            <p className="text-xs text-slate-600 font-mono mt-0.5">
              ID: {activeEvaluation.evaluation_id}
            </p>
          </div>
        </div>
        <Link
          to="/evaluations/$id"
          params={{ id: activeEvaluation.evaluation_id }}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-sm bg-[#1b3b87] px-4 text-xs font-bold uppercase tracking-wider text-white transition-colors hover:bg-[#1b3b87]/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87] shrink-0"
        >
          <span>View Progress</span>
          <ArrowRight className="size-4" aria-hidden="true" />
        </Link>
      </div>
    );
  }

  if (latestReadyDocument) {
    return (
      <div className="rounded-sm border border-slate-200 bg-white p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-start gap-3.5">
          <div className="flex size-10 items-center justify-center rounded-sm border border-[#15803d]/30 bg-[#15803d]/10 text-[#15803d] shrink-0 mt-0.5">
            <PlayCircle className="size-5" aria-hidden="true" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center rounded-sm bg-[#15803d] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">
                Ready to Evaluate
              </span>
              {latestReadyDocument.program && (
                <span className="text-xs text-slate-500 font-semibold">
                  {latestReadyDocument.program}
                </span>
              )}
            </div>
            <h3 className="mt-1 text-base font-bold text-slate-900">
              {latestReadyDocument.title}
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Document is processed and ready for automated quality review.
            </p>
          </div>
        </div>
        <Link
          to="/documents/$documentId/evaluation"
          params={{ documentId: latestReadyDocument.documentId }}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-sm bg-[#1b3b87] px-4 text-xs font-bold uppercase tracking-wider text-white transition-colors hover:bg-[#1b3b87]/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87] shrink-0"
        >
          <span>Start Evaluation</span>
          <ArrowRight className="size-4" aria-hidden="true" />
        </Link>
      </div>
    );
  }

  return null;
}
