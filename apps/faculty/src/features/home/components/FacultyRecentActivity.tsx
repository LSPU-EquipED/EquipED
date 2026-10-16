import { Link } from "@tanstack/react-router";
import { ArrowRight } from "@phosphor-icons/react";
import { isTargetAgent, TARGET_AGENT_META } from "@equiped/types";
import { Skeleton } from "@equiped/ui";
import type { HomeEvaluationItem } from "../types";
import { formatDateOnly, getEvaluationStatusBadge } from "../utils/homeData";

export function FacultyRecentActivity({
  evaluations,
  isLoading,
}: {
  evaluations: HomeEvaluationItem[];
  isLoading: boolean;
}) {
  // Each entry is one run; preserve failed attempts and their specialist context.
  const recent = [...evaluations]
    .sort(
      (a, b) =>
        (Date.parse(b.submitted_at) || 0) - (Date.parse(a.submitted_at) || 0),
    )
    .slice(0, 3);

  return (
    <section
      className="dashboard-activity dashboard-panel"
      aria-labelledby="dashboard-activity-heading"
      aria-busy={isLoading}
    >
      <div className="mb-1 flex items-center justify-between gap-4">
        <h2
          id="dashboard-activity-heading"
          className="text-base font-semibold text-text"
        >
          Recent activity
        </h2>
        <Link
          to="/evaluations"
          className="dashboard-link inline-flex min-h-10 items-center gap-2 text-sm font-medium text-primary hover:underline"
        >
          View history <ArrowRight size={16} aria-hidden="true" />
        </Link>
      </div>
      {isLoading ? (
        <div role="status" className="space-y-4 py-5">
          <span className="sr-only">Loading recent activity</span>
          {[0, 1, 2].map((key) => (
            <Skeleton key={key} className="h-12 w-full" />
          ))}
        </div>
      ) : recent.length ? (
        <ul className="divide-y divide-border border-t border-border">
          {recent.map((evaluation) => {
            const status = getEvaluationStatusBadge(evaluation.status).label;
            const specialist = isTargetAgent(evaluation.target_agent)
              ? TARGET_AGENT_META[evaluation.target_agent].shortLabel
              : "Evaluation";
            const tone =
              evaluation.status.toUpperCase() === "FAILED"
                ? "text-destructive"
                : evaluation.status.toUpperCase() === "COMPLETED"
                  ? "text-success"
                  : "text-text-muted";
            return (
              <li key={evaluation.evaluation_id}>
                <Link
                  to="/evaluations/$id"
                  params={{ id: evaluation.evaluation_id }}
                  className="dashboard-link group flex flex-wrap items-center justify-between gap-x-5 gap-y-2 py-4"
                >
                  <span className="min-w-0 flex-1 basis-48">
                    <span className="block break-words text-sm font-medium leading-relaxed text-text group-hover:text-primary">
                      {evaluation.document_title || "Untitled module"}
                    </span>
                    <span className="mt-1 flex flex-wrap items-center gap-x-2 text-sm text-text-muted">
                      <span>{specialist}</span>
                      <span aria-hidden="true">·</span>
                      <time dateTime={evaluation.submitted_at}>
                        {formatDateOnly(evaluation.submitted_at)}
                      </time>
                    </span>
                  </span>
                  <span className={`text-sm font-medium ${tone}`}>
                    {status}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="border-t border-border py-6 text-sm leading-relaxed text-text-muted">
          No evaluations yet. Choose a specialist workspace to review your first
          module.
        </p>
      )}
    </section>
  );
}
