import { useNavigate } from '@tanstack/react-router';
import {
  Books,
  CaretRight,
  ClockCounterClockwise,
  GitFork,
  GraduationCap,
} from '@phosphor-icons/react';
import { Button } from '@/shared/components/Button';
import { Skeleton } from '@/shared/components/Skeleton';
import { cn } from '@/shared/components/utils';

export interface FacultyLaunchpadsProps {
  totalModules?: number;
  readyModules?: number;
  inProgressCount?: number;
  actionRequiredCount?: number;
  isLoading?: boolean;
}

export function FacultyLaunchpads({
  totalModules = 0,
  readyModules = 0,
  inProgressCount = 0,
  actionRequiredCount = 0,
  isLoading = false,
}: FacultyLaunchpadsProps = {}) {
  const navigate = useNavigate();

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4.5 items-stretch">
      {/* ── LEFT HERO: Primary SLM Storage Hub (Spans 6 of 12 Columns) ───── */}
      <div className="lg:col-span-6 xl:col-span-7 rounded-md border border-border bg-surface p-5 sm:p-6 flex flex-col justify-between gap-5 shadow-none hover:border-primary/40 transition-colors">
        <div className="space-y-3.5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <div className="flex size-9 items-center justify-center rounded-sm bg-primary/10 border border-primary/20 text-primary shrink-0">
                <Books className="size-4.5" aria-hidden="true" />
              </div>
              <h2 className="text-base font-bold text-text tracking-tight">
                SLM Storage Repository
              </h2>
            </div>
            <span className="inline-flex items-center text-[10px] font-bold uppercase tracking-wider text-primary font-mono bg-primary/10 border border-primary/20 px-2 py-0.5 rounded-xs">
              Core Storage
            </span>
          </div>

          <p className="text-xs text-text-muted leading-relaxed max-w-xl">
            Manage course modules, inspect chapter outlines, and verify OCR indexing.
          </p>

          {/* Unified Sunken Repository Health Tray (Clean, Borderless Key-Value Strip) */}
          <div className="rounded-sm bg-surface-subtle/70 p-3.5 grid grid-cols-2 sm:grid-cols-4 gap-3">
            {/* Total Modules */}
            <div className="space-y-0.5">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted font-mono block">
                Total Modules
              </span>
              <p className="text-xl sm:text-2xl font-bold tracking-tight text-text tabular-nums">
                {isLoading ? <Skeleton className="h-7 w-10" /> : totalModules}
              </p>
            </div>

            {/* Ready for Review */}
            <div className="space-y-0.5">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted font-mono block">
                Ready for Review
              </span>
              <p className="text-xl sm:text-2xl font-bold tracking-tight text-success tabular-nums">
                {isLoading ? <Skeleton className="h-7 w-10" /> : readyModules}
              </p>
            </div>

            {/* In Ingestion */}
            <div className="space-y-0.5">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted font-mono block">
                In Ingestion
              </span>
              <p className="text-xl sm:text-2xl font-bold tracking-tight text-info tabular-nums">
                {isLoading ? <Skeleton className="h-7 w-10" /> : inProgressCount}
              </p>
            </div>

            {/* Action Required */}
            <div className="space-y-0.5">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted font-mono block">
                Action Required
              </span>
              <p
                className={cn(
                  'text-xl sm:text-2xl font-bold tracking-tight tabular-nums',
                  actionRequiredCount > 0 ? 'text-warning' : 'text-text-muted',
                )}
              >
                {isLoading ? <Skeleton className="h-7 w-10" /> : actionRequiredCount}
              </p>
            </div>
          </div>
        </div>

        {/* Storage action */}
        <div className="flex flex-col sm:flex-row items-center gap-2.5 pt-1">

          <Button
            type="button"
            variant="secondary"
            size="sm"
            aria-label="Open SLM Storage Repository"
            className="w-full sm:w-auto flex-1 justify-between font-semibold text-xs h-9.5 px-3.5 border-border hover:border-primary/40 hover:bg-surface-subtle transition-colors cursor-pointer"
            onClick={() => navigate({ to: '/documents' })}
          >
            <span>Open Storage</span>
            <CaretRight
              className="size-3.5 shrink-0 text-text-muted group-hover:text-primary transition-colors"
              aria-hidden="true"
            />
          </Button>
        </div>
      </div>

      {/* ── RIGHT COLUMN: Compliance & Audit Tools (Spans 6 of 12 Columns) ─ */}
      <div className="lg:col-span-6 xl:col-span-5 flex flex-col justify-between gap-4.5">
        {/* Top Half: 2-Column Subgrid for Curriculum & Syllabus */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4.5 flex-1">
          {/* Tile 2: Curriculum Alignment */}
          <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-4 shadow-none hover:border-border-strong transition-colors">
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-2">
                <div className="flex size-9 items-center justify-center rounded-sm bg-surface-subtle border border-border text-text-muted shrink-0">
                  <GraduationCap className="size-4.5" aria-hidden="true" />
                </div>
                <span className="inline-flex items-center text-[10px] font-semibold uppercase tracking-wider text-text-muted font-mono bg-surface-subtle border border-border px-1.5 py-0.5 rounded-xs">
                  Curriculum Map
                </span>
              </div>

              <div>
                <h2 className="text-sm font-bold text-text tracking-tight">Curriculum Alignment</h2>
                <p className="text-xs text-text-muted mt-1 leading-relaxed">
                  Verify prerequisite maps and curriculum compliance.
                </p>
              </div>
            </div>

            <Button
              type="button"
              variant="secondary"
              size="md"
              aria-label="Open Curriculum Alignment Workspace"
              className="group w-full justify-between font-semibold text-xs h-9 px-3 border-border hover:bg-surface-subtle transition-colors cursor-pointer"
              onClick={() => navigate({ to: '/alignment' })}
            >
              <span className="truncate whitespace-nowrap">Curriculum Check</span>
              <CaretRight
                className="size-3.5 shrink-0 text-text-muted group-hover:text-text transition-colors"
                aria-hidden="true"
              />
            </Button>
          </div>

          {/* Tile 3: Syllabus Alignment */}
          <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-4 shadow-none hover:border-border-strong transition-colors">
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-2">
                <div className="flex size-9 items-center justify-center rounded-sm bg-surface-subtle border border-border text-text-muted shrink-0">
                  <GitFork className="size-4.5" aria-hidden="true" />
                </div>
                <span className="inline-flex items-center text-[10px] font-semibold uppercase tracking-wider text-text-muted font-mono bg-surface-subtle border border-border px-1.5 py-0.5 rounded-xs">
                  Syllabus Audit
                </span>
              </div>

              <div>
                <h2 className="text-sm font-bold text-text tracking-tight">Syllabus Alignment</h2>
                <p className="text-xs text-text-muted mt-1 leading-relaxed">
                  Check topic coverage against approved syllabi.
                </p>
              </div>
            </div>

            <Button
              type="button"
              variant="secondary"
              size="md"
              aria-label="Open Syllabus Alignment Workspace"
              className="group w-full justify-between font-semibold text-xs h-9 px-3 border-border hover:bg-surface-subtle transition-colors cursor-pointer"
              onClick={() => navigate({ to: '/syllabus-alignment' })}
            >
              <span className="truncate whitespace-nowrap">Alignment Check</span>
              <CaretRight
                className="size-3.5 shrink-0 text-text-muted group-hover:text-text transition-colors"
                aria-hidden="true"
              />
            </Button>
          </div>
        </div>

        {/* Bottom Half: Evaluation History & Scorecards (Full-Width of Right Column) */}
        <div className="rounded-md border border-border bg-surface p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-none hover:border-border-strong transition-colors">
          <div className="flex items-start gap-3">
            <div className="flex size-9 items-center justify-center rounded-sm bg-surface-subtle border border-border text-text-muted shrink-0">
              <ClockCounterClockwise className="size-4.5" aria-hidden="true" />
            </div>
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-text tracking-tight">Evaluation History</h2>
                <span className="inline-flex items-center text-[10px] font-semibold uppercase tracking-wider text-text-muted font-mono bg-surface-subtle border border-border px-1.5 py-0.5 rounded-xs">
                  Archived QA
                </span>
              </div>
              <p className="text-xs text-text-muted leading-relaxed">
                Access previous QA scorecards, adjectival ratings, and official PDF exports.
              </p>
            </div>
          </div>

          <Button
            type="button"
            variant="secondary"
            size="sm"
            aria-label="View Evaluation History"
            className="group shrink-0 font-semibold text-xs h-9 px-4 border-border hover:bg-surface-subtle transition-colors cursor-pointer"
            onClick={() => navigate({ to: '/evaluations' })}
          >
            <span>View History</span>
            <CaretRight
              className="size-3.5 shrink-0 text-text-muted group-hover:text-text transition-colors"
              aria-hidden="true"
            />
          </Button>
        </div>
      </div>
    </div>
  );
}
