import { WarningCircle } from "@phosphor-icons/react";
import { Button } from "@equiped/ui";

interface SpecialistEvaluationFailureProps {
  errorMessage?: string | null;
  onRetry: () => void;
}

export function SpecialistEvaluationFailure({
  errorMessage,
  onRetry,
}: SpecialistEvaluationFailureProps) {
  return (
    <section
      role="alert"
      className="rounded-md border border-destructive/30 bg-destructive-soft p-6 sm:p-8"
    >
      <div className="flex items-start gap-3">
        <WarningCircle
          className="mt-0.5 size-5 shrink-0 text-destructive"
          aria-hidden="true"
        />
        <div className="min-w-0 space-y-3">
          <h2 className="text-lg font-semibold text-text">
            Evaluation could not be completed
          </h2>
          <p className="max-w-xl break-words text-sm leading-relaxed text-text-muted">
            {errorMessage ||
              "The evaluation stopped before it could produce a result. Review the submission details and try again."}
          </p>
          <Button size="sm" onClick={onRetry}>
            Try again
          </Button>
        </div>
      </div>
    </section>
  );
}
