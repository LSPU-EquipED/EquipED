import { useEffect, useMemo, useState } from "react";
import { useSubmitCriterionFeedback } from "./useSubmitFeedback";
import {
  buildCriterionFeedbackActions,
  initialDrafts,
  isDifferentFromOriginal,
} from "../utils/criterionReview";
import type { CriterionReviewDraft, CriterionScoreItem } from "../types";

interface UseCriterionReviewOptions {
  agentName: string;
  evaluationId: string;
  criteria: readonly CriterionScoreItem[];
  onClose: () => void;
  onDirtyChange?: (dirty: boolean) => void;
}

export function useCriterionReview({
  agentName,
  evaluationId,
  criteria,
  onClose,
  onDirtyChange,
}: UseCriterionReviewOptions) {
  const baseline = useMemo(() => initialDrafts(criteria), [criteria]);
  const [drafts, setDrafts] = useState<Record<string, CriterionReviewDraft>>(
    () => baseline,
  );
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const hasUnsavedChanges = criteria.some((criterion) => {
    const draft = drafts[criterion.criterion_id];
    const initial = baseline[criterion.criterion_id];
    return (
      draft.score !== initial.score ||
      draft.justification !== initial.justification ||
      draft.rejected !== initial.rejected ||
      Object.entries(draft.itemRejections).some(
        ([id, rejected]) => rejected !== initial.itemRejections[id],
      )
    );
  });
  useEffect(() => {
    onDirtyChange?.(hasUnsavedChanges);
  }, [hasUnsavedChanges, onDirtyChange]);
  const mutation = useSubmitCriterionFeedback(evaluationId);

  function updateDraft(
    criterionId: string,
    patch: Partial<CriterionReviewDraft>,
  ) {
    setDrafts((prev) => ({
      ...prev,
      [criterionId]: { ...prev[criterionId], ...patch },
    }));
  }

  function selectScore(criterion: CriterionScoreItem, value: number) {
    updateDraft(criterion.criterion_id, { score: value, expanded: true });
  }

  function toggleRejected(criterion: CriterionScoreItem) {
    const draft = drafts[criterion.criterion_id];
    const nextRejected = !draft.rejected;
    updateDraft(criterion.criterion_id, {
      rejected: nextRejected,
      expanded: nextRejected ? false : draft.expanded,
    });
  }

  function toggleItemsExpanded(criterion: CriterionScoreItem) {
    const draft = drafts[criterion.criterion_id];
    updateDraft(criterion.criterion_id, {
      itemsExpanded: !draft.itemsExpanded,
    });
  }

  function toggleItem(criterion: CriterionScoreItem, itemId: string) {
    const draft = drafts[criterion.criterion_id];
    updateDraft(criterion.criterion_id, {
      itemRejections: {
        ...draft.itemRejections,
        [itemId]: !draft.itemRejections[itemId],
      },
    });
  }

  function revertCriterion(criterion: CriterionScoreItem) {
    updateDraft(criterion.criterion_id, {
      score: criterion.score ?? undefined,
      justification: criterion.justification,
      rejected: false,
      expanded: false,
    });
  }

  // A criterion that isn't flagged as incorrect must keep a non-empty
  // justification -- an empty EDIT justification is rejected by the backend
  // (422) and, if it ever slipped through as whitespace, would pollute DPO
  // training data. Block submission per-criterion instead of surfacing a
  // generic post-submit failure.
  const emptyJustificationIds = criteria
    .filter((criterion) => {
      const draft = drafts[criterion.criterion_id];
      return !draft.rejected && draft.justification.trim() === "";
    })
    .map((criterion) => criterion.criterion_id);
  const hasEmptyJustification = emptyJustificationIds.length > 0;

  const editedCount = criteria.filter((criterion) =>
    isDifferentFromOriginal(criterion, drafts[criterion.criterion_id]),
  ).length;
  const flaggedCount = criteria.filter(
    (criterion) => drafts[criterion.criterion_id].rejected,
  ).length;
  const draftSubtotal = criteria.length
    ? criteria.reduce(
        (sum, criterion) => sum + drafts[criterion.criterion_id].score,
        0,
      ) / criteria.length
    : 0;

  async function handleSubmit() {
    setSubmitError(null);

    if (hasEmptyJustification) {
      setSubmitError(
        "Justification cannot be empty. Fix the highlighted criteria below.",
      );
      return;
    }

    const actions = buildCriterionFeedbackActions(criteria, drafts, agentName);

    if (actions.length === 0) {
      onClose();
      return;
    }

    setIsSubmitting(true);
    // Retry-all on partial failure: PreferenceLog is append-only and the
    // exporter dedups to the latest edit per criterion, so re-sending an
    // already-succeeded action on retry is harmless, not a duplicate bug.
    const results = await Promise.allSettled(
      actions.map((entry) => mutation.mutateAsync(entry)),
    );
    setIsSubmitting(false);

    if (results.some((result) => result.status === "rejected")) {
      setSubmitError("Some corrections couldn't be saved. Please try again.");
      return;
    }

    onClose();
  }

  return {
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
  };
}
