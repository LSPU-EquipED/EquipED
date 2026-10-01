import { Check } from "@phosphor-icons/react";
import { cn } from "@equiped/ui";

const STAGE_LABELS: Record<string, string> = {
  SUBMITTED: "Queued",
  PREPROCESSING: "Preparing the module",
  EVALUATING: "Specialist review",
  SYNTHESIZING: "Finalizing results",
};

export function EvaluationStageTracker({
  status,
  specialistLabel,
}: {
  status: string;
  specialistLabel: string;
}) {
  const stages = Object.entries(STAGE_LABELS);
  const currentStage = stages.findIndex(
    ([stageStatus]) => stageStatus === status,
  );

  return (
    <>
      <ol className="my-6" aria-label="Evaluation stages">
        {stages.map(([status, label], index) => (
          <li
            key={status}
            aria-current={index === currentStage ? "step" : undefined}
            className={cn(
              "relative flex items-start gap-3 text-sm",
              index < stages.length - 1 && "pb-5",
            )}
          >
            {index < stages.length - 1 && (
              <span
                aria-hidden="true"
                className="absolute bottom-0 left-2.5 top-5 w-px bg-border"
              />
            )}
            <span
              aria-hidden="true"
              className={cn(
                "relative flex size-5 shrink-0 items-center justify-center rounded-full border",
                index === currentStage
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-surface text-text-muted",
              )}
            >
              {index < currentStage ? (
                <Check className="size-3" />
              ) : (
                <span
                  className={cn(
                    "size-1.5 rounded-full",
                    index === currentStage
                      ? "bg-primary-foreground"
                      : "bg-border",
                  )}
                />
              )}
            </span>
            <span
              className={cn(
                index === currentStage
                  ? "font-medium text-primary"
                  : "text-text-muted",
              )}
            >
              {label}
            </span>
          </li>
        ))}
      </ol>
      <p
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {specialistLabel} · {STAGE_LABELS[status] ?? "In progress"}
      </p>
    </>
  );
}
