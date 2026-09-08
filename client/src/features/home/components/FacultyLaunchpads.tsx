import { useNavigate } from '@tanstack/react-router';
import {
  Books,
  CaretRight,
  ClockCounterClockwise,
  GitFork,
  GraduationCap,
} from '@phosphor-icons/react';
import { Button } from '@/shared/components/Button';

export function FacultyLaunchpads() {
  const navigate = useNavigate();

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {/* 1. SLM Storage Repository */}
      <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-4 shadow-none">
        <div className="flex items-start gap-3">
          <div className="flex size-9 items-center justify-center rounded-sm bg-primary/10 border border-primary/20 text-primary shrink-0">
            <Books className="size-4.5" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-text tracking-tight">SLM Storage Repository</h2>
            <p className="text-xs text-text-muted mt-1 leading-relaxed">
              Manage course modules, inspect chapter outlines, and verify OCR indexing.
            </p>
          </div>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="md"
          aria-label="Open SLM Storage Repository"
          className="group w-full justify-between font-semibold text-xs sm:text-sm h-10 px-3.5 border-border hover:border-primary/50 hover:bg-primary-soft hover:text-primary transition-colors cursor-pointer"
          onClick={() => navigate({ to: '/documents' })}
        >
          <span className="truncate whitespace-nowrap">Open Storage</span>
          <CaretRight
            className="size-4 shrink-0 text-text-muted group-hover:text-primary transition-colors"
            aria-hidden="true"
          />
        </Button>
      </div>

      {/* 2. Curriculum Alignment Workspace */}
      <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-4 shadow-none">
        <div className="flex items-start gap-3">
          <div className="flex size-9 items-center justify-center rounded-sm bg-info/10 border border-info/20 text-info shrink-0">
            <GraduationCap className="size-4.5" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-text tracking-tight">Curriculum Alignment</h2>
            <p className="text-xs text-text-muted mt-1 leading-relaxed">
              Verify prerequisite mappings and curriculum compliance across academic programs.
            </p>
          </div>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="md"
          aria-label="Open Curriculum Alignment Workspace"
          className="group w-full justify-between font-semibold text-xs sm:text-sm h-10 px-3.5 border-border hover:border-info/50 hover:bg-info-soft hover:text-info transition-colors cursor-pointer"
          onClick={() => navigate({ to: '/alignment' })}
        >
          <span className="truncate whitespace-nowrap">Curriculum Check</span>
          <CaretRight
            className="size-4 shrink-0 text-text-muted group-hover:text-info transition-colors"
            aria-hidden="true"
          />
        </Button>
      </div>

      {/* 3. Syllabus Alignment Workspace */}
      <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-4 shadow-none">
        <div className="flex items-start gap-3">
          <div className="flex size-9 items-center justify-center rounded-sm bg-warning/10 border border-warning/20 text-warning shrink-0">
            <GitFork className="size-4.5" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-text tracking-tight">Syllabus Alignment</h2>
            <p className="text-xs text-text-muted mt-1 leading-relaxed">
              Check topic coverage and align SLM content directly against course syllabi.
            </p>
          </div>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="md"
          aria-label="Open Syllabus Alignment Workspace"
          className="group w-full justify-between font-semibold text-xs sm:text-sm h-10 px-3.5 border-border hover:border-warning/50 hover:bg-warning-soft hover:text-warning transition-colors cursor-pointer"
          onClick={() => navigate({ to: '/syllabus-alignment' })}
        >
          <span className="truncate whitespace-nowrap">Alignment Check</span>
          <CaretRight
            className="size-4 shrink-0 text-text-muted group-hover:text-warning transition-colors"
            aria-hidden="true"
          />
        </Button>
      </div>

      {/* 4. Evaluation History & Scorecards */}
      <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-4 shadow-none">
        <div className="flex items-start gap-3">
          <div className="flex size-9 items-center justify-center rounded-sm bg-success/10 border border-success/20 text-success shrink-0">
            <ClockCounterClockwise className="size-4.5" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-text tracking-tight">Evaluation History</h2>
            <p className="text-xs text-text-muted mt-1 leading-relaxed">
              Access previous QA scorecards, adjectival ratings, and official PDF exports.
            </p>
          </div>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="md"
          aria-label="View Evaluation History"
          className="group w-full justify-between font-semibold text-xs sm:text-sm h-10 px-3.5 border-border hover:border-success/50 hover:bg-success-soft hover:text-success transition-colors cursor-pointer"
          onClick={() => navigate({ to: '/evaluations' })}
        >
          <span className="truncate whitespace-nowrap">View History</span>
          <CaretRight
            className="size-4 shrink-0 text-text-muted group-hover:text-success transition-colors"
            aria-hidden="true"
          />
        </Button>
      </div>
    </div>
  );
}
