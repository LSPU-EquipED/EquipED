import { Link } from '@tanstack/react-router';
import { ArrowRight, Loader2, PlayCircle } from 'lucide-react';
import { Badge } from '@/shared/components/Badge';
import { TYPOGRAPHY } from '@/shared/constants/theme';
import type { FacultyHomeData } from '../types';
import { formatDateTime } from '../utils/homeData';
interface ActiveEvaluationBannerProps {
  homeData: FacultyHomeData;
}

export function ActiveEvaluationBanner({ homeData }: ActiveEvaluationBannerProps) {
  const { activeEvaluation, latestReadyDocument } = homeData;

  if (activeEvaluation) {
    return (
      <div className="rounded-md border border-info/30 bg-info-soft p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-start gap-3.5">
          <div className="flex size-10 items-center justify-center rounded-sm border border-info/30 bg-surface text-info shrink-0 mt-0.5">
            <Loader2 className="size-5 animate-spin" aria-hidden="true" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <Badge variant="info">
                Active Evaluation
              </Badge>
              <span className="text-xs text-text-muted font-medium">
                Submitted {formatDateTime(activeEvaluation.submitted_at)}
              </span>
            </div>
            <h3 className={TYPOGRAPHY.headingSm + ' mt-1'}>
              {activeEvaluation.document_title || 'Untitled SLM'}
            </h3>
            <p className="text-xs text-text-muted font-mono mt-0.5">
              ID: {activeEvaluation.evaluation_id}
            </p>
          </div>
        </div>
        <Link
          to="/evaluations/$id"
          params={{ id: activeEvaluation.evaluation_id }}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-sm bg-primary px-4 text-xs font-semibold uppercase tracking-wider text-primary-foreground transition-colors hover:bg-primary-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring shrink-0"
        >
          <span>View Progress</span>
          <ArrowRight className="size-4" aria-hidden="true" />
        </Link>
      </div>
    );
  }

  if (latestReadyDocument) {
    return (
      <div className="rounded-md border border-border bg-surface p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-start gap-3.5">
          <div className="flex size-10 items-center justify-center rounded-sm border border-success/30 bg-success-soft text-success shrink-0 mt-0.5">
            <PlayCircle className="size-5" aria-hidden="true" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <Badge variant="success">
                Ready to Evaluate
              </Badge>
              {latestReadyDocument.program && (
                <span className="text-xs text-text-muted font-semibold">
                  {latestReadyDocument.program}
                </span>
              )}
            </div>
            <h3 className={TYPOGRAPHY.headingSm + ' mt-1'}>
              {latestReadyDocument.title}
            </h3>
            <p className="text-xs text-text-muted mt-0.5">
              Document is processed and ready for automated quality review.
            </p>
          </div>
        </div>
        <Link
          to="/documents/$documentId/evaluation"
          params={{ documentId: latestReadyDocument.documentId }}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-sm bg-primary px-4 text-xs font-semibold uppercase tracking-wider text-primary-foreground transition-colors hover:bg-primary-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring shrink-0"
        >
          <span>Start Evaluation</span>
          <ArrowRight className="size-4" aria-hidden="true" />
        </Link>
      </div>
    );
  }

  return null;
}
