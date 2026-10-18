import { useId, useState } from "react";
import { ArrowClockwise, ArrowRight, CaretDown } from "@phosphor-icons/react";
import { Button, Skeleton } from "@equiped/ui";
import type { DeskQueueItem } from "../../types";
import unavailableArt from "../../../../assets/illustrations/specialists/workspace/workspace-unavailable.svg";
import interruptedArt from "../../../../assets/illustrations/specialists/workspace/review-interrupted.svg";

export function WorkspaceLoading({
  label = "specialist workspace",
}: { label?: string } = {}) {
  return (
    <section
      className="swp-landing swp-loading"
      role="status"
      aria-label={`Loading ${label}`}
      aria-busy="true"
    >
      <div className="swp-welcome" aria-hidden="true">
        <div className="swp-welcome-copy swp-loading-copy">
          <Skeleton className="h-7 w-3/4" />
          <Skeleton className="h-7 w-3/5" />
          <div className="swp-loading-description">
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-4/5" />
          </div>
          <Skeleton className="swp-loading-cta h-10 w-36" />
        </div>
        <div className="swp-welcome-art">
          <Skeleton className="swp-loading-art" />
        </div>
      </div>
      <div className="swp-counts" aria-hidden="true">
        {[0, 1, 2].map((n) => (
          <div key={n}>
            <Skeleton className="h-3 w-3/4" />
            <Skeleton className="h-6 w-6" />
          </div>
        ))}
      </div>
      <div className="swp-recent" aria-hidden="true">
        <div className="swp-section-heading">
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-3 w-20" />
        </div>
        <ul className="swp-module-list">
          {[0, 1, 2].map((n) => (
            <li key={n}>
              <div className="swp-module-copy swp-loading-row">
                <Skeleton className="h-4 w-4/5" />
                <Skeleton className="h-3 w-3/5" />
              </div>
              <Skeleton className="h-3 w-20" />
              <div className="swp-loading-action">
                <Skeleton className="h-3 w-16" />
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

type RecoveryProps = { onRetry: () => void } & (
  | { kind: "workspace" }
  | {
      kind: "evaluation";
      item?: Pick<DeskQueueItem, "title">;
      errorMessage?: string | null;
    }
);

export function WorkspaceRecovery(props: RecoveryProps) {
  const titleId = useId();
  const detailsId = useId();
  const [detailsOpen, setDetailsOpen] = useState(false);
  const evaluation = props.kind === "evaluation";
  return (
    <section className="swp-recovery" aria-labelledby={titleId}>
      {evaluation && props.item && (
        <div className="swp-recovery-context">{props.item.title}</div>
      )}
      <div className="swp-recovery-body">
        <div className="swp-recovery-art">
          <img
            src={evaluation ? interruptedArt : unavailableArt}
            alt=""
            aria-hidden="true"
          />
        </div>
        <div className="swp-recovery-copy">
          <div role="alert">
            <h1 id={titleId}>
              {evaluation
                ? "The evaluation couldn’t finish."
                : "Unable to load this workspace."}
            </h1>
            <p>
              {evaluation
                ? "This run has no saved findings. Review the setup before starting another evaluation."
                : "We couldn’t retrieve your modules. Try again to reload the workspace."}
            </p>
          </div>
          <Button onClick={props.onRetry}>
            {evaluation ? "Review setup" : "Try again"}
            {evaluation ? (
              <ArrowRight size={16} aria-hidden="true" />
            ) : (
              <ArrowClockwise size={16} aria-hidden="true" />
            )}
          </Button>
        </div>
      </div>
      {evaluation && (
        <div className="swp-failure-details">
          <button
            type="button"
            onClick={() => setDetailsOpen(!detailsOpen)}
            aria-expanded={detailsOpen}
            aria-controls={detailsId}
          >
            Failure details
            <CaretDown size={16} aria-hidden="true" />
          </button>
          <div
            id={detailsId}
            role="region"
            aria-label="Failure details"
            aria-hidden={!detailsOpen}
            {...(!detailsOpen ? { inert: "" } : {})}
            className={`animate-ledger-collapse ${detailsOpen ? "animate-ledger-collapse-expanded" : "animate-ledger-collapse-collapsed"}`}
          >
            <div className="swp-failure-details-content">
              <p>
                {props.errorMessage ||
                  "The specialist stopped before completing its review. No scores or partial result were saved."}
              </p>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
