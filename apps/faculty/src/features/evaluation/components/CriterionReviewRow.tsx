import { CaretRight, Flag } from "@phosphor-icons/react";
import { cn } from "@equiped/ui";
import { formatScore } from "../utils/scoreHelpers";
import type { CriterionReviewDraft, CriterionScoreItem } from "../types";

interface CriterionReviewRowProps {
  criterion: CriterionScoreItem;
  draft: CriterionReviewDraft;
  isEdited: boolean;
  isJustificationEmpty: boolean;
  onSelectScore: (value: number) => void;
  onToggleRejected: () => void;
  onToggleItems: () => void;
  onToggleItem: (itemId: string) => void;
  onRevert: () => void;
  onJustificationChange: (value: string) => void;
}

function scoreButtonClasses(
  value: number,
  selected: boolean,
  isEdited: boolean,
): string {
  if (!selected) {
    return "border-border text-text-muted hover:bg-surface-subtle";
  }
  if (isEdited) {
    return "border-primary bg-primary text-primary-foreground";
  }
  return value < 2
    ? "border-destructive bg-destructive text-destructive-foreground"
    : "border-success bg-success text-success-foreground";
}

export function CriterionReviewRow({
  criterion,
  draft,
  isEdited,
  isJustificationEmpty,
  onSelectScore,
  onToggleRejected,
  onToggleItems,
  onToggleItem,
  onRevert,
  onJustificationChange,
}: CriterionReviewRowProps) {
  // A criterion already persisted as REJECT has no backend path to
  // retract it -- toggling the flag off here would only change
  // local draft state, never reach the server, and reappear as
  // flagged the next time the modal opens. Lock the toggle instead
  // of offering an affordance that silently does nothing.
  const alreadyRejected = criterion.reviewer_correction?.action === "REJECT";

  return (
    <div className="grid gap-2 rounded-sm border border-border p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-text">
            {criterion.criterion_text}
          </span>
          {isEdited && (
            <span className="rounded-full bg-primary-soft px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-primary">
              Edited
            </span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {[1, 2, 3, 4].map((value) => (
            <button
              key={value}
              type="button"
              disabled={draft.rejected}
              onClick={() => onSelectScore(value)}
              className={cn(
                "inline-flex size-6 items-center justify-center rounded-sm border text-xs font-bold disabled:cursor-not-allowed disabled:opacity-40 tabular-nums",
                scoreButtonClasses(value, draft.score === value, isEdited),
              )}
            >
              {value}
            </button>
          ))}
          <button
            type="button"
            title={
              alreadyRejected
                ? "Already flagged as incorrect — cannot be retracted here"
                : "Flag as incorrect"
            }
            disabled={alreadyRejected}
            onClick={() => onToggleRejected()}
            className={cn(
              "inline-flex size-6 shrink-0 items-center justify-center rounded-sm border disabled:cursor-not-allowed",
              draft.rejected
                ? "border-destructive bg-destructive-soft text-destructive"
                : "border-border text-text-muted hover:bg-surface-subtle",
            )}
          >
            <Flag className="size-3.5" />
          </button>
        </div>
      </div>

      {!draft.expanded && (
        <p className="text-xs leading-relaxed text-text-muted">
          {criterion.justification}
        </p>
      )}

      {draft.expanded && !draft.rejected && (
        <div className="grid gap-1">
          <label className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
            Justification
            <textarea
              className={cn(
                "mt-1 block w-full rounded-sm border bg-surface px-2 py-1 text-xs text-text focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
                isJustificationEmpty
                  ? "border-destructive focus-visible:ring-destructive"
                  : "border-border",
              )}
              rows={2}
              maxLength={4000}
              value={draft.justification}
              onChange={(event) => onJustificationChange(event.target.value)}
            />
            {isJustificationEmpty && (
              <span className="mt-1 block text-[10px] font-normal normal-case tracking-normal text-destructive">
                Justification cannot be empty.
              </span>
            )}
          </label>
          <p className="text-[11px] text-text-muted">
            AI scored {formatScore(criterion.score)}/4 —{" "}
            {criterion.justification}.{" "}
            <button
              type="button"
              className="font-semibold text-primary hover:underline"
              onClick={() => onRevert()}
            >
              Revert
            </button>
          </p>
        </div>
      )}

      {criterion.raw_items &&
        criterion.raw_items.length > 0 &&
        !draft.rejected && (
          <div className="grid gap-1 rounded-sm border border-border/60 bg-surface-subtle p-2">
            <button
              type="button"
              className="flex w-full items-center justify-between gap-2 text-left"
              onClick={() => onToggleItems()}
              aria-expanded={draft.itemsExpanded}
            >
              <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
                What counted toward this score
                {typeof criterion.corrected_score === "number" && (
                  <span className="ml-2 font-normal normal-case tracking-normal text-text-muted">
                    (recalculates to {formatScore(criterion.corrected_score)}/4
                    on save)
                  </span>
                )}
              </span>
              <CaretRight
                className={cn(
                  "size-3.5 shrink-0 text-text-muted transition-transform",
                  draft.itemsExpanded && "rotate-90",
                )}
              />
            </button>

            {draft.itemsExpanded && (
              <>
                <p className="text-[11px] normal-case tracking-normal text-text-muted">
                  These are the specific things the AI found while checking
                  &ldquo;
                  {criterion.criterion_text}&rdquo;. Uncheck anything that
                  shouldn&apos;t count toward this score.
                </p>
                <ul className="grid gap-1 mt-1">
                  {criterion.raw_items.map((item) => {
                    const isRejected =
                      draft.itemRejections[item.item_id] ?? item.rejected;
                    return (
                      <li
                        key={item.item_id}
                        className="flex items-start gap-2 text-xs"
                      >
                        <input
                          type="checkbox"
                          className="mt-0.5 shrink-0"
                          checked={!isRejected}
                          onChange={() => onToggleItem(item.item_id)}
                          aria-label={
                            isRejected
                              ? "Mark item as counted"
                              : "Mark item as not counted"
                          }
                        />
                        <span
                          className={cn(
                            "leading-snug",
                            isRejected && "text-text-muted line-through",
                          )}
                        >
                          {item.text}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </>
            )}
          </div>
        )}
    </div>
  );
}
