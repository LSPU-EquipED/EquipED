import { useEffect, useRef, useState } from "react";
import { X } from "@phosphor-icons/react";
import { ConfirmationModal } from "@equiped/ui";
import { useCriterionReview } from "../hooks/useCriterionReview";
import { isDifferentFromOriginal } from "../utils/criterionReview";
import { formatScore } from "../utils/scoreHelpers";
import { CriterionReviewRow } from "./CriterionReviewRow";
import type { CriterionScoreItem } from "../types";

type AgentReviewModalProps = {
  readonly agentName: string;
  readonly evaluationId: string;
  readonly criteria: readonly CriterionScoreItem[];
  readonly onClose: () => void;
  readonly onDirtyChange?: (dirty: boolean) => void;
};

export function AgentReviewModal(props: AgentReviewModalProps) {
  const { agentName, criteria, onClose } = props;
  const dialogRef = useRef<HTMLDivElement>(null);
  const [showDiscard, setShowDiscard] = useState(false);
  const {
    drafts,
    submitError,
    isSubmitting,
    hasUnsavedChanges,
    emptyJustificationIds,
    hasEmptyJustification,
    editedCount,
    flaggedCount,
    draftSubtotal,
    updateDraft,
    selectScore,
    toggleRejected,
    toggleItemsExpanded,
    toggleItem,
    revertCriterion,
    handleSubmit,
  } = useCriterionReview(props);
  const agentLabel = agentName.toUpperCase();
  const requestClose = () => {
    if (!isSubmitting) {
      if (hasUnsavedChanges) setShowDiscard(true);
      else onClose();
    }
  };
  useEffect(() => {
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialogRef.current
      ?.querySelector<HTMLButtonElement>('button[title="Close"]')
      ?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected)
        previousFocus.focus();
    };
  }, []);

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-label={`Review ${agentLabel} scores`}
      className="fixed inset-0 z-50 flex items-center justify-center bg-overlay/50 p-4"
      onKeyDown={(event) => {
        if (showDiscard || event.defaultPrevented) return;
        if (event.key === "Escape") {
          event.preventDefault();
          requestClose();
        }
        if (event.key === "Tab") {
          const nodes = dialogRef.current?.querySelectorAll<HTMLElement>(
            "button:not([disabled]), input:not([disabled]), textarea:not([disabled])",
          );
          if (!nodes?.length) return;
          const first = nodes[0],
            last = nodes[nodes.length - 1];
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
          }
        }
      }}
    >
      <ConfirmationModal
        isOpen={showDiscard}
        title="Discard unsaved changes?"
        description="Your score edits have not been saved. Keep editing or discard them before leaving this review."
        variant="warning"
        confirmLabel="Discard changes"
        cancelLabel="Keep editing"
        onClose={() => setShowDiscard(false)}
        onConfirm={onClose}
      />
      <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-sm border border-border bg-surface shadow-none">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wider text-text">
              Review {agentLabel} Scores
            </h2>
            <p className="mt-0.5 text-[11px] text-text-muted">
              {editedCount} of {criteria.length} edited · subtotal{" "}
              {formatScore(draftSubtotal)}/4
            </p>
          </div>
          <button
            type="button"
            title="Close"
            aria-label="Close review"
            className="inline-flex size-7 items-center justify-center rounded-sm text-text-muted hover:bg-surface-subtle hover:text-text"
            onClick={requestClose}
            disabled={isSubmitting}
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="grid gap-3 px-5 py-4">
          {criteria.map((criterion) => (
            <CriterionReviewRow
              key={criterion.criterion_id}
              criterion={criterion}
              draft={drafts[criterion.criterion_id]}
              isEdited={isDifferentFromOriginal(
                criterion,
                drafts[criterion.criterion_id],
              )}
              isJustificationEmpty={emptyJustificationIds.includes(
                criterion.criterion_id,
              )}
              onSelectScore={(value) => selectScore(criterion, value)}
              onToggleRejected={() => toggleRejected(criterion)}
              onToggleItems={() => toggleItemsExpanded(criterion)}
              onToggleItem={(itemId) => toggleItem(criterion, itemId)}
              onRevert={() => revertCriterion(criterion)}
              onJustificationChange={(justification) =>
                updateDraft(criterion.criterion_id, { justification })
              }
            />
          ))}
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-border px-5 py-4">
          <p className="text-[11px] text-text-muted">
            {submitError ? (
              <span className="font-semibold text-destructive">
                {submitError}
              </span>
            ) : (
              `${flaggedCount} flagged · ${editedCount} edited`
            )}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded-sm border border-border px-3 py-1.5 text-[10px] font-bold uppercase tracking-wide text-text-muted hover:bg-surface-subtle hover:text-text"
              onClick={requestClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="button"
              className="rounded-sm bg-primary px-3 py-1.5 text-[10px] font-bold uppercase tracking-wide text-primary-foreground hover:bg-primary-strong disabled:opacity-50"
              onClick={handleSubmit}
              disabled={isSubmitting || hasEmptyJustification}
            >
              {isSubmitting ? "Saving…" : "Save changes"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
