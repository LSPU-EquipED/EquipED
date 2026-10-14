import type {
  CriterionFeedbackRequest,
  CriterionReviewDraft,
  CriterionScoreItem,
} from "../types";

function baselineFor(criterion: CriterionScoreItem): {
  score: number;
  justification: string;
} {
  if (criterion.reviewer_correction?.action === "EDIT") {
    return {
      score: criterion.reviewer_correction.score ?? criterion.score,
      justification:
        criterion.reviewer_correction.justification ?? criterion.justification,
    };
  }
  return { score: criterion.score, justification: criterion.justification };
}

export function initialDrafts(
  criteria: readonly CriterionScoreItem[],
): Record<string, CriterionReviewDraft> {
  return Object.fromEntries(
    criteria.map((c) => {
      const baseline = baselineFor(c);
      const isEditBaseline = c.reviewer_correction?.action === "EDIT";
      return [
        c.criterion_id,
        {
          score: baseline.score,
          justification: baseline.justification,
          rejected: c.reviewer_correction?.action === "REJECT",
          expanded: isEditBaseline,
          itemsExpanded: false,
          itemRejections: Object.fromEntries(
            (c.raw_items ?? []).map((item) => [item.item_id, item.rejected]),
          ),
        },
      ];
    }),
  );
}

// The edited indicator compares against the generated original; submission compares
// against the saved correction. Reopening an untouched correction must still show
// as edited without issuing another request on Save.
export function isDifferentFromOriginal(
  criterion: CriterionScoreItem,
  draft: CriterionReviewDraft,
): boolean {
  if (draft.rejected) return false;
  return (
    draft.score !== criterion.score ||
    draft.justification.trim() !== criterion.justification.trim()
  );
}

export function buildCriterionFeedbackActions(
  criteria: readonly CriterionScoreItem[],
  drafts: Record<string, CriterionReviewDraft>,
  agentName: string,
): { criterionId: string; body: CriterionFeedbackRequest }[] {
  const scoreActions = criteria
    .map((criterion) => {
      const draft = drafts[criterion.criterion_id];
      const wasRejected = criterion.reviewer_correction?.action === "REJECT";

      if (draft.rejected) {
        // Only send REJECT if this is a new rejection this session --
        // reopening an already-rejected, untouched criterion and
        // resubmitting must send zero requests, same as any other
        // unchanged criterion.
        if (wasRejected) return null;
        return {
          criterionId: criterion.criterion_id,
          body: { agent_name: agentName, action: "REJECT" as const },
        };
      }

      const baseline = baselineFor(criterion);
      const trimmedJustification = draft.justification.trim();
      const scoreChanged = draft.score !== baseline.score;
      const justificationChanged =
        trimmedJustification !== baseline.justification.trim();
      if (scoreChanged || justificationChanged) {
        return {
          criterionId: criterion.criterion_id,
          body: {
            agent_name: agentName,
            action: "EDIT" as const,
            score: draft.score,
            justification: trimmedJustification,
          },
        };
      }
      return null;
    })
    .filter((entry): entry is NonNullable<typeof entry> => entry !== null);

  // Item-level corrections (SME/Coordinator raw_items only): only send an
  // action for items whose local toggle actually differs from what's
  // already persisted, same "unchanged = zero requests" rule as above.
  const itemActions = criteria.flatMap((criterion) => {
    const draft = drafts[criterion.criterion_id];
    if (!criterion.raw_items || draft.rejected) return [];
    return criterion.raw_items
      .filter((item) => draft.itemRejections[item.item_id] !== item.rejected)
      .map((item) => ({
        criterionId: criterion.criterion_id,
        body: {
          agent_name: agentName,
          action: draft.itemRejections[item.item_id]
            ? ("ITEM_REJECT" as const)
            : ("ITEM_ACCEPT" as const),
          item_id: item.item_id,
        },
      }));
  });

  return [...scoreActions, ...itemActions];
}
