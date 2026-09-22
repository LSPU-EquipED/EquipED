import { Link } from '@tanstack/react-router';
import { ArrowUpRight, BookOpenText, GitFork } from '@phosphor-icons/react';
import { useEvaluatorWorkstation } from '../hooks/useEvaluatorWorkstation';

export interface FacultyLaunchpadsProps {
  evaluatorPermissions?: readonly string[] | null;
  userRole?: string;
}

export function FacultyLaunchpads({ evaluatorPermissions, userRole }: FacultyLaunchpadsProps) {
  const { allowedSpecialists } = useEvaluatorWorkstation(evaluatorPermissions, userRole);
  return (
    <aside aria-label="Evaluation tools" className="min-w-0 space-y-6 xl:border-l xl:border-border xl:pl-6">
      <section aria-labelledby="specialist-heading">
        <h2 id="specialist-heading" className="text-xs font-semibold uppercase tracking-wider text-text">
          Evaluation workspaces
        </h2>
        <div className="mt-2.5 divide-y divide-border rounded-md border border-border bg-surface overflow-hidden shadow-none">
          {allowedSpecialists.map((specialist) => {
            const Icon = specialist.icon;
            return (
              <Link
                key={specialist.id}
                to="/specialists/$agentId"
                params={{ agentId: specialist.id }}
                className="group flex items-center gap-3 p-3 transition-colors hover:bg-surface-subtle/70 focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
              >
                <div className="flex size-8 shrink-0 items-center justify-center rounded-xs border border-border bg-surface-subtle/50 text-primary transition-colors group-hover:border-primary/30 group-hover:bg-primary-soft/30">
                  <Icon className="size-4.5" aria-hidden="true" />
                </div>
                <span className="min-w-0 flex-1">
                  <span className="block text-xs font-semibold text-text transition-colors group-hover:text-primary">
                    {specialist.label}
                  </span>
                  <span className="mt-0.5 block text-[11px] leading-snug text-text-muted">
                    {specialist.desc}
                  </span>
                </span>
                <ArrowUpRight className="size-3.5 shrink-0 text-text-muted transition-colors group-hover:text-primary" aria-hidden="true" />
              </Link>
            );
          })}
        </div>
      </section>

      <section aria-labelledby="alignment-heading">
        <h2 id="alignment-heading" className="text-xs font-semibold uppercase tracking-wider text-text">
          Alignment checks
        </h2>
        <div className="mt-2.5 divide-y divide-border rounded-md border border-border bg-surface overflow-hidden shadow-none">
          <Link
            to="/syllabus-alignment"
            className="group flex items-center gap-3 p-3 text-xs font-semibold text-text transition-colors hover:bg-surface-subtle/70 hover:text-primary focus-visible:outline-2 focus-visible:outline-ring"
          >
            <div className="flex size-7.5 shrink-0 items-center justify-center rounded-xs border border-border bg-surface-subtle/50 text-text-muted transition-colors group-hover:border-primary/30 group-hover:bg-primary-soft/30 group-hover:text-primary">
              <BookOpenText className="size-4" aria-hidden="true" />
            </div>
            <span className="flex-1">Syllabus alignment</span>
            <ArrowUpRight className="size-3.5 text-text-muted transition-colors group-hover:text-primary" aria-hidden="true" />
          </Link>
          <Link
            to="/curriculum-alignment"
            className="group flex items-center gap-3 p-3 text-xs font-semibold text-text transition-colors hover:bg-surface-subtle/70 hover:text-primary focus-visible:outline-2 focus-visible:outline-ring"
          >
            <div className="flex size-7.5 shrink-0 items-center justify-center rounded-xs border border-border bg-surface-subtle/50 text-text-muted transition-colors group-hover:border-primary/30 group-hover:bg-primary-soft/30 group-hover:text-primary">
              <GitFork className="size-4" aria-hidden="true" />
            </div>
            <span className="flex-1">Curriculum check</span>
            <ArrowUpRight className="size-3.5 text-text-muted transition-colors group-hover:text-primary" aria-hidden="true" />
          </Link>
        </div>
      </section>

      <div className="rounded-sm border border-border/70 bg-surface-subtle/40 p-3 text-[11px] leading-relaxed text-text-muted">
        Automated evaluations are advisory. Final decisions remain with institutional reviewers.
      </div>
    </aside>
  );
}
