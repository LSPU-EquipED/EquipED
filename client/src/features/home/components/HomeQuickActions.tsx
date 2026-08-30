import { Link } from '@tanstack/react-router';
import {
  ArrowRight,
  ClipboardList,
  FolderOpen,
  ListChecks,
  Upload,
} from 'lucide-react';
import { TYPOGRAPHY } from '@/shared/constants/theme';

export function HomeQuickActions() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {/* Upload SLM (Primary) */}
      <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex size-10 items-center justify-center rounded-sm border border-primary/20 bg-primary-soft text-primary shrink-0">
            <Upload className="size-5" aria-hidden="true" />
          </div>
          <div>
            <h3 className={TYPOGRAPHY.headingSm}>Upload SLM</h3>
            <p className="text-xs text-text-muted mt-0.5 leading-relaxed">
              Submit a learning module for automated evaluation.
            </p>
          </div>
        </div>
        <Link
          to="/upload"
          className="inline-flex h-9 w-full items-center justify-between rounded-sm bg-primary px-3 text-xs font-semibold uppercase tracking-wider text-primary-foreground hover:bg-primary-strong transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span>Upload Material</span>
          <ArrowRight className="size-3.5" aria-hidden="true" />
        </Link>
      </div>

      {/* My SLMs */}
      <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex size-10 items-center justify-center rounded-sm border border-border bg-surface-subtle text-text shrink-0">
            <FolderOpen className="size-5" aria-hidden="true" />
          </div>
          <div>
            <h3 className={TYPOGRAPHY.headingSm}>My SLMs</h3>
            <p className="text-xs text-text-muted mt-0.5 leading-relaxed">
              View uploaded modules and start evaluations.
            </p>
          </div>
        </div>
        <Link
          to="/documents"
          className="inline-flex h-9 w-full items-center justify-between rounded-sm border border-border bg-surface px-3 text-xs font-semibold uppercase tracking-wider text-text hover:bg-surface-subtle transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span>Open My SLMs</span>
          <ArrowRight className="size-3.5 text-text-muted" aria-hidden="true" />
        </Link>
      </div>

      {/* Evaluations */}
      <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex size-10 items-center justify-center rounded-sm border border-border bg-surface-subtle text-text shrink-0">
            <ClipboardList className="size-5" aria-hidden="true" />
          </div>
          <div>
            <h3 className={TYPOGRAPHY.headingSm}>Evaluations</h3>
            <p className="text-xs text-text-muted mt-0.5 leading-relaxed">
              Review completed scorecards and reports.
            </p>
          </div>
        </div>
        <Link
          to="/evaluations"
          className="inline-flex h-9 w-full items-center justify-between rounded-sm border border-border bg-surface px-3 text-xs font-semibold uppercase tracking-wider text-text hover:bg-surface-subtle transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span>View All Evaluations</span>
          <ArrowRight className="size-3.5 text-text-muted" aria-hidden="true" />
        </Link>
      </div>

      {/* Alignment Tools */}
      <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex size-10 items-center justify-center rounded-sm border border-border bg-surface-subtle text-text shrink-0">
            <ListChecks className="size-5" aria-hidden="true" />
          </div>
          <div>
            <h3 className={TYPOGRAPHY.headingSm}>Syllabus Alignment</h3>
            <p className="text-xs text-text-muted mt-0.5 leading-relaxed">
              Check module coverage against syllabus outcomes.
            </p>
          </div>
        </div>
        <Link
          to="/syllabus-alignment"
          className="inline-flex h-9 w-full items-center justify-between rounded-sm border border-border bg-surface px-3 text-xs font-semibold uppercase tracking-wider text-text hover:bg-surface-subtle transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span>Check Alignment</span>
          <ArrowRight className="size-3.5 text-text-muted" aria-hidden="true" />
        </Link>
      </div>
    </div>
  );
}
