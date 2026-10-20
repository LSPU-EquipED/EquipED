import {
  ITSO_CRITERION_NAMES,
  type ITSOCriterionAssessment,
} from "@equiped/types";
import type { MatrixCriterionScoreItem } from "../types";

/** Read-only archived observations for the existing criteria inspection view. */
export function historicalITSOCriteria(
  criteria: readonly ITSOCriterionAssessment[],
): MatrixCriterionScoreItem[] {
  return criteria.map((criterion) => ({
    criterion_id: criterion.criterion_id,
    criterion_text: ITSO_CRITERION_NAMES[criterion.criterion_id],
    score: criterion.score,
    justification: [
      ...new Set([
        ...criterion.evidence.map((fact) => fact.value),
        ...criterion.concerns,
        ...(criterion.score_withheld_reason
          ? [`Score withheld: ${criterion.score_withheld_reason}`]
          : []),
        ...criterion.uncertainties,
      ]),
    ].join("\n\n"),
    evidence:
      criterion.evidence
        .flatMap((fact) =>
          fact.source_spans.map((span) => span.quote).filter(Boolean),
        )
        .join("\n\n") || null,
  }));
}
