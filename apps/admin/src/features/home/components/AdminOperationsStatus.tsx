import { CheckCircle, Clock, Warning } from "@phosphor-icons/react";
import { Skeleton } from "@equiped/ui";
import type { SystemSummaryResponse } from "../types";

export function AdminOperationsStatus({
  summary,
  isLoading,
  isError,
}: {
  summary?: SystemSummaryResponse;
  isLoading: boolean;
  isError: boolean;
}) {
  if (isLoading) {
    return (
      <div
        role="status"
        aria-label="Loading evaluation queue"
        className="space-y-2 border-l-2 border-border bg-surface p-4"
      >
        <Skeleton className="h-4 w-52" />
        <Skeleton className="h-3 w-72 max-w-full" />
      </div>
    );
  }
  if (isError || !summary) return null;

  const active = summary.active_evaluations;
  const failed = summary.failed_evaluations;
  const Icon = failed > 0 ? Warning : active > 0 ? Clock : CheckCircle;
  const tone =
    failed > 0
      ? "border-warning text-warning"
      : active > 0
        ? "border-info text-info"
        : "border-success text-success";

  return (
    <section
      aria-label="Evaluation queue"
      className={`flex items-start gap-3 border-l-2 bg-surface p-4 ${tone}`}
    >
      <Icon className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
      <div>
        <h2 className="text-sm font-semibold text-text">
          {failed > 0
            ? "Failed runs need inspection"
            : active > 0
              ? "Evaluations are in progress"
              : "No evaluations in progress"}
        </h2>
        <p className="mt-1 text-xs leading-relaxed text-text-muted">
          {active > 0
            ? `${active} evaluation${active === 1 ? " is" : "s are"} queued or running. `
            : failed > 0
              ? "No active runs in the evaluation queue. "
              : "The evaluation queue is clear. "}
          {failed > 0
            ? `${failed} failed run${failed === 1 ? " is" : "s are"} recorded. Inspect the monitoring matrix for details.`
            : "New faculty evaluations will appear in the matrix."}
        </p>
      </div>
    </section>
  );
}
