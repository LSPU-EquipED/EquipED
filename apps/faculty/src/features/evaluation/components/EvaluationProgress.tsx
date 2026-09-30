import { Check, Clock } from "@phosphor-icons/react";
import { cn } from "@equiped/ui";
import { TARGET_AGENT_META, type TargetAgent } from "@equiped/types";
import {
  EVALUATION_STAGES,
  SPECIALIST_REVIEW_COPY,
} from "../utils/evaluationProgress";
import { EvaluationProgressVisual } from "./EvaluationProgressVisual";

interface EvaluationProgressProps {
  status?: string;
  targetAgent?: TargetAgent | "all";
  documentTitle?: string;
}

/** Uses only server-reported stages; it does not estimate completion or duration. */
export function EvaluationProgress({
  status,
  targetAgent,
  documentTitle,
}: EvaluationProgressProps) {
  const currentIndex = EVALUATION_STAGES.findIndex(
    (stage) => stage.status === status,
  );
  const currentStage = EVALUATION_STAGES[currentIndex];
  const specialistLabel =
    targetAgent && targetAgent !== "all"
      ? `${TARGET_AGENT_META[targetAgent].shortLabel} specialist`
      : targetAgent === "all"
        ? "Specialist team"
        : "Specialist";
  const description =
    status === "EVALUATING"
      ? targetAgent && targetAgent !== "all"
        ? SPECIALIST_REVIEW_COPY[targetAgent]
        : "The specialists are reviewing your module against the applicable rubrics, with evidence to support each finding."
      : (currentStage?.description ??
        "Waiting for the latest evaluation stage.");
  return (
    <div className="w-full">
      <section
        aria-label={
          documentTitle
            ? `Evaluation progress for ${documentTitle}`
            : "Evaluation progress"
        }
        className="grid overflow-hidden rounded-md border border-border bg-surface lg:min-h-[32rem] lg:grid-cols-[14rem_minmax(0,1fr)]"
      >
        <div className="flex flex-col justify-center border-b border-border bg-surface-subtle/35 p-5 lg:border-b-0 lg:border-r lg:p-6">
          <ol
            aria-label="Evaluation stages"
            className="grid grid-cols-1 gap-1 sm:grid-cols-2 lg:grid-cols-1 lg:gap-4"
          >
            {EVALUATION_STAGES.map(({ label }, index) => (
              <li
                key={label}
                aria-current={index === currentIndex ? "step" : undefined}
              >
                <div
                  className={cn(
                    "flex min-h-12 items-center gap-3 rounded-sm px-2 text-sm",
                    index === currentIndex
                      ? "bg-primary-soft font-semibold text-primary"
                      : "text-text-muted",
                  )}
                >
                  <span
                    aria-hidden="true"
                    className={cn(
                      "flex size-6 shrink-0 items-center justify-center text-xs tabular-nums",
                      index < currentIndex
                        ? "text-success"
                        : index === currentIndex
                          ? "rounded-sm bg-primary text-primary-foreground"
                          : "text-text-muted",
                    )}
                  >
                    {index < currentIndex ? (
                      <Check className="size-4" weight="bold" />
                    ) : (
                      String(index + 1).padStart(2, "0")
                    )}
                  </span>
                  {label}
                  <span className="sr-only">
                    {index < currentIndex
                      ? ", done"
                      : index === currentIndex
                        ? ", in progress"
                        : ", pending"}
                  </span>
                </div>
              </li>
            ))}
          </ol>
        </div>

        <div className="flex min-w-0 flex-col justify-center px-5 py-7 sm:px-8 sm:py-8 lg:px-10">
          <div className="mx-auto w-full max-w-2xl">
            <EvaluationProgressVisual
              specialistLabel={specialistLabel}
              targetAgent={targetAgent}
              isActive={currentIndex >= 0}
            />
            <div
              role="status"
              aria-live="polite"
              aria-atomic="true"
              className="space-y-2 border-t border-border pt-5"
            >
              <h2 className="text-xl font-semibold leading-snug text-text">
                {currentStage?.heading ?? "Checking evaluation status"}
              </h2>
              <p className="max-w-lg text-sm leading-relaxed text-text-muted">
                {description}
              </p>
            </div>
          </div>
        </div>
      </section>

      <p className="mt-4 flex items-start gap-2 text-sm leading-relaxed text-text-muted">
        <Clock className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        Evaluation continues in the background. You can return from your
        dashboard.
      </p>
    </div>
  );
}
