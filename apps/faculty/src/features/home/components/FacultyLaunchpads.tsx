import { useNavigate } from '@tanstack/react-router';
import {
  Books,
  CaretRight,
  ClockCounterClockwise,
  GitFork,
  GraduationCap,
  UserCheck,
} from '@phosphor-icons/react';
import { Button } from '@equiped/ui';
import { useEvaluatorWorkstation } from '../hooks/useEvaluatorWorkstation';

export interface FacultyLaunchpadsProps {
  evaluatorPermissions?: readonly string[] | null;
  userRole?: string;
}

export function FacultyLaunchpads({
  evaluatorPermissions,
  userRole = 'faculty',
}: FacultyLaunchpadsProps = {}) {
  const navigate = useNavigate();
  const { allowedSpecialists, hasSingleSpecialist, singleSpecialist } =
    useEvaluatorWorkstation(evaluatorPermissions, userRole);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-stretch">
      {/* ── Left Workstation: SLM Storage & Permission-Scoped Specialist (7 of 12) ─── */}
      <div className="lg:col-span-7 rounded-md border border-border bg-surface p-6 flex flex-col justify-between gap-5 transition-colors hover:border-primary/40">
        <div className="space-y-5">
          {/* Header */}
          <div className="flex items-start gap-3">
            <div className="flex size-9 items-center justify-center rounded-sm bg-primary/10 border border-primary/20 text-primary shrink-0 mt-0.5">
              <Books className="size-5" aria-hidden="true" />
            </div>
            <div className="space-y-0.5">
              <h2 className="text-base font-bold text-text tracking-tight">
                SLM Storage Repository
              </h2>
              <p className="text-xs text-text-muted leading-relaxed">
                Manage learning modules, review extraction health, and track syllabus mapping.
              </p>
            </div>
          </div>

          {/* Single Specialist Role Assigned */}
          {hasSingleSpecialist && singleSpecialist ? (
            <div className="space-y-2">
              <span className="text-xs font-semibold text-text-muted block">
                Your Assigned Evaluation Workstation
              </span>
              <div className="rounded-sm border border-border bg-surface-subtle/40 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="flex size-9 items-center justify-center rounded-sm bg-primary text-primary-foreground shrink-0">
                    <UserCheck className="size-4.5" aria-hidden="true" />
                  </div>
                  <div className="space-y-0.5 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-text">
                        {singleSpecialist.label}
                      </span>
                      <span className="rounded-xs bg-primary/10 border border-primary/20 px-1.5 py-0.2 text-[10px] font-bold text-primary font-mono">
                        {singleSpecialist.short}
                      </span>
                    </div>
                    <p className="text-xs text-text-muted leading-normal truncate">
                      {singleSpecialist.desc}
                    </p>
                  </div>
                </div>

                <Button
                  type="button"
                  variant="primary"
                  size="sm"
                  onClick={() =>
                    void navigate({
                      to: '/specialists/$agentId',
                      params: { agentId: singleSpecialist.id },
                    })
                  }
                  className="h-9 px-4 text-xs font-semibold gap-1.5 shrink-0"
                >
                  <span>Open {singleSpecialist.short} Workspace</span>
                  <CaretRight className="size-3" aria-hidden="true" />
                </Button>
              </div>
            </div>
          ) : allowedSpecialists.length > 1 ? (
            /* Multi-Specialist Grid for Authorized Evaluators */
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-text-muted block">
                  Automated Evaluation Specialists
                </span>
                <span className="text-[11px] text-text-muted">
                  Select domain to inspect
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {allowedSpecialists.map((spec) => {
                  const IconComponent = spec.icon;
                  return (
                    <button
                      key={spec.id}
                      type="button"
                      onClick={() =>
                        void navigate({
                          to: '/specialists/$agentId',
                          params: { agentId: spec.id },
                        })
                      }
                      className="group flex items-start gap-3 rounded-sm border border-border bg-surface-subtle/50 p-3 text-left transition-colors hover:border-primary/40 hover:bg-surface-subtle cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <div className="flex size-7 shrink-0 items-center justify-center rounded-xs bg-surface border border-border text-primary mt-0.5 group-hover:border-primary/30 transition-colors">
                        <IconComponent className="size-3.5" aria-hidden="true" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-1">
                          <span className="text-xs font-semibold text-text truncate group-hover:text-primary transition-colors">
                            {spec.label}
                          </span>
                          <CaretRight className="size-3 text-text-muted shrink-0 group-hover:text-primary group-hover:translate-x-0.5 transition-all" aria-hidden="true" />
                        </div>
                        <p className="text-[11px] text-text-muted mt-0.5 leading-snug line-clamp-1">
                          {spec.desc}
                        </p>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : (
            /* General Submitting Faculty View */
            <div className="space-y-1.5">
              <span className="text-xs font-semibold text-text-muted block">
                Evaluation Pipeline Standards
              </span>
              <div className="rounded-sm border border-border bg-surface-subtle/50 p-3 text-xs text-text-muted leading-relaxed">
                Uploaded modules undergo automated rubric review across Subject Matter Expert, Program Coordinator, Gender &amp; Development, and ITSO compliance domains.
              </div>
            </div>
          )}
        </div>

        {/* Bottom row */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
          <p className="text-xs text-text-muted leading-normal">
            Inspect OCR page extractions and course materials
          </p>

          <div className="flex items-center gap-2 shrink-0">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => navigate({ to: '/documents' })}
              className="h-8.5 px-3.5 text-xs font-semibold gap-1.5 border-border hover:bg-surface-subtle"
            >
              <span>Open Storage</span>
              <CaretRight className="size-3 text-text-muted" aria-hidden="true" />
            </Button>
          </div>
        </div>
      </div>

      {/* ── Right Workstation: Alignment & Evaluation History (5 of 12) ── */}
      <div className="lg:col-span-5 flex flex-col justify-between gap-4">
        {/* Curriculum Alignment & Syllabus Alignment Subgrid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 flex-1">
          {/* Tile: Curriculum Alignment */}
          <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-4 transition-colors hover:border-border-strong">
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <div className="flex size-8 items-center justify-center rounded-sm bg-surface-subtle border border-border text-text-muted shrink-0">
                  <GraduationCap className="size-4" aria-hidden="true" />
                </div>
                <h3 className="text-sm font-bold text-text tracking-tight">Curriculum Alignment</h3>
              </div>
              <p className="text-xs text-text-muted leading-relaxed">
                Verify prerequisite maps and curriculum compliance.
              </p>
            </div>

            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => navigate({ to: '/alignment' })}
              className="w-full justify-between h-9 px-3 text-xs font-semibold border-border hover:bg-surface-subtle"
            >
              <span>Curriculum Check</span>
              <CaretRight className="size-3 text-text-muted" aria-hidden="true" />
            </Button>
          </div>

          {/* Tile: Syllabus Alignment */}
          <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-4 transition-colors hover:border-border-strong">
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <div className="flex size-8 items-center justify-center rounded-sm bg-surface-subtle border border-border text-text-muted shrink-0">
                  <GitFork className="size-4" aria-hidden="true" />
                </div>
                <h3 className="text-sm font-bold text-text tracking-tight">Syllabus Alignment</h3>
              </div>
              <p className="text-xs text-text-muted leading-relaxed">
                Check topic coverage against approved syllabi.
              </p>
            </div>

            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => navigate({ to: '/syllabus-alignment' })}
              className="w-full justify-between h-9 px-3 text-xs font-semibold border-border hover:bg-surface-subtle"
            >
              <span>Alignment Check</span>
              <CaretRight className="size-3 text-text-muted" aria-hidden="true" />
            </Button>
          </div>
        </div>

        {/* Tile: Evaluation History */}
        <div className="rounded-md border border-border bg-surface p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition-colors hover:border-border-strong">
          <div className="flex items-start gap-3">
            <div className="flex size-8 items-center justify-center rounded-sm bg-surface-subtle border border-border text-text-muted shrink-0 mt-0.5">
              <ClockCounterClockwise className="size-4" aria-hidden="true" />
            </div>
            <div className="space-y-0.5">
              <h3 className="text-sm font-bold text-text tracking-tight">Evaluation History</h3>
              <p className="text-xs text-text-muted leading-relaxed">
                Access previous QA scorecards, adjectival ratings, and official PDF exports.
              </p>
            </div>
          </div>

          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => navigate({ to: '/evaluations' })}
            className="shrink-0 h-9 px-3.5 text-xs font-semibold border-border hover:bg-surface-subtle"
          >
            <span>View History</span>
            <CaretRight className="size-3 text-text-muted" aria-hidden="true" />
          </Button>
        </div>
      </div>
    </div>
  );
}
