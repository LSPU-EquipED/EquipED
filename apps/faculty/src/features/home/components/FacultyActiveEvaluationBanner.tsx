import { Link } from "@tanstack/react-router";
import { ArrowRight } from "@phosphor-icons/react";
import { isTargetAgent, TARGET_AGENT_META } from "@equiped/types";
import type { HomeEvaluationItem } from "../types";
import { EvaluationStageTracker } from "./EvaluationStageTracker";

export function FacultyActiveEvaluationBanner({
  evaluation,
}: {
  evaluation: HomeEvaluationItem | null;
}) {
  if (!evaluation) return null;

  const agent = isTargetAgent(evaluation.target_agent)
    ? evaluation.target_agent
    : null;
  const specialistLabel = agent
    ? TARGET_AGENT_META[agent].shortLabel
    : "Evaluation";
  const destination = agent
    ? {
        to: "/specialists/$agentId/$documentId" as const,
        params: { agentId: agent, documentId: evaluation.document_id },
      }
    : {
        to: "/evaluations/$id" as const,
        params: { id: evaluation.evaluation_id },
      };

  return (
    <section
      aria-label="Current evaluation"
      className="rounded-md border border-border bg-surface p-5 sm:p-6"
    >
      <p className="flex items-center gap-2 text-sm font-medium text-primary">
        <span className="size-1.5 rounded-full bg-primary" aria-hidden="true" />
        In progress
      </p>
      <h2 className="mt-4 break-words text-base font-semibold leading-relaxed text-text">
        {evaluation.document_title || "Untitled module"}
      </h2>
      <p className="mt-1 text-sm text-text-muted">{specialistLabel}</p>
      <EvaluationStageTracker
        status={evaluation.status}
        specialistLabel={specialistLabel}
      />
      <Link
        {...destination}
        className="inline-flex min-h-10 w-full items-center justify-between gap-2 rounded-sm border border-border bg-surface px-3 text-sm font-medium text-text transition-colors hover:border-primary/40 hover:bg-primary-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        View progress <ArrowRight className="size-4" aria-hidden="true" />
      </Link>
    </section>
  );
}
