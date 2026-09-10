import { Link } from '@tanstack/react-router';
import {
  CheckCircle,
  Clock,
  Play,
  Spinner,
} from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
import { cn } from '@/shared/components/utils';
import { BUTTON_STYLES } from '@/shared/constants/theme';
import type { TargetAgentMeta } from '@/shared/types/evaluations';
import type { DeskQueueItem } from '../types';

function formatUploadDate(dateString?: string | null): string {
  if (!dateString) return '—';
  try {
    const d = new Date(dateString);
    if (Number.isNaN(d.getTime())) return '—';
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return '—';
  }
}

export interface SpecialistDirectoryViewProps {
  items: DeskQueueItem[];
  validAgent: string;
  meta: TargetAgentMeta;
}

export function SpecialistDirectoryView({
  items,
  validAgent,
  meta,
}: SpecialistDirectoryViewProps) {
  if (items.length === 0) {
    return (
      <div className="rounded-md border border-border bg-surface p-12 text-center flex flex-col items-center justify-center space-y-4 max-w-xl mx-auto my-8">
        <div className="flex size-14 items-center justify-center rounded-sm bg-success-soft text-success border border-success/30">
          <CheckCircle className="size-7 text-success" aria-hidden="true" />
        </div>
        <div className="space-y-1">
          <h2 className="text-base font-bold text-text">No Pending Evaluations</h2>
          <p className="text-xs text-text-muted max-w-md mx-auto leading-relaxed">
            All course modules in your SLM storage have been evaluated for the {meta.fullName} desk. View completed evaluation scorecards in Evaluation History.
          </p>
        </div>
        <Link
          to="/evaluations"
          className={cn(
            BUTTON_STYLES.base,
            BUTTON_STYLES.variants.primary,
            BUTTON_STYLES.sizes.md,
            'font-bold text-xs uppercase tracking-wider gap-2 mt-2'
          )}
        >
          <Clock className="size-4" aria-hidden="true" />
          <span>View Evaluation History</span>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between border-b border-border pb-3">
        <div className="flex items-center gap-2.5">
          <h2 className="text-sm font-bold uppercase tracking-wider text-text">
            Modules to Evaluate
          </h2>
          <Badge variant="neutral">{items.length}</Badge>
        </div>
        <span className="text-xs text-text-muted">
          Select a module to begin evaluation
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {items.map((item) => {
          const rawStatus = (item.my_status || '').toUpperCase();
          const isItemEvaluating = rawStatus === 'EVALUATING';

          return (
            <div
              key={item.document_id}
              className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-4 hover:border-primary/40 transition-colors"
            >
              <div className="space-y-2.5">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-xs font-bold text-text line-clamp-2 leading-snug">
                    {item.title}
                  </span>
                  {isItemEvaluating ? (
                    <Badge variant="warning" className="shrink-0 flex items-center gap-1">
                      <Spinner className="size-2.5 animate-spin" aria-hidden="true" />
                      <span>Evaluating</span>
                    </Badge>
                  ) : (
                    <Badge variant="info" className="shrink-0">
                      Ready
                    </Badge>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-muted font-mono">
                  <span>{item.course_code || 'General'}</span>
                  {item.program && (
                    <>
                      <span>•</span>
                      <span>{item.program}</span>
                    </>
                  )}
                  <span>•</span>
                  <span>Uploaded {formatUploadDate(item.uploaded_at)}</span>
                </div>
              </div>

              <div className="pt-2 border-t border-border flex items-center justify-between">
                <Link
                  to="/specialists/$agentId/$documentId"
                  params={{ agentId: validAgent, documentId: item.document_id }}
                  className={cn(
                    BUTTON_STYLES.base,
                    BUTTON_STYLES.variants.primary,
                    BUTTON_STYLES.sizes.sm,
                    'text-xs font-semibold gap-1.5'
                  )}
                >
                  {isItemEvaluating ? (
                    <>
                      <Spinner className="size-3.5 animate-spin" aria-hidden="true" />
                      <span>View Progress</span>
                    </>
                  ) : (
                    <>
                      <Play className="size-3.5 fill-current" weight="fill" aria-hidden="true" />
                      <span>Start Evaluation</span>
                    </>
                  )}
                </Link>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
