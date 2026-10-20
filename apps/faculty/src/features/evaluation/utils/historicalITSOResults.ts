import {
  ITSO_CRITERION_NAMES,
  type ITSOAssessment,
  type EvaluationResultsResponse,
} from "@equiped/types";

/** Present archived evidence-only runs in the existing scorecard without inventing scores. */
export function historicalITSOResults(
  assessment: ITSOAssessment,
): EvaluationResultsResponse {
  const failed = assessment.execution_status === "FAILED";
  return {
    evaluation_id: assessment.evaluation_id,
    document_id: assessment.document_id,
    synthesized_score: null,
    overall_score: assessment.subtotal,
    evaluation_status: assessment.execution_status,
    active_agents: ["itso"],
    failed_agents: failed ? ["itso"] : [],
    is_partial: false,
    flags: [],
    legacy_notice: failed
      ? "This historical evaluation failed. Available observations are diagnostic only."
      : "Historical evidence-only evaluation. Unavailable scores remain unscored; re-evaluate to use the current rubric review.",
    domain_scores: {
      itso: {
        form_snapshot_id: assessment.form_snapshot_id,
        adapter_key: "itso",
        adapter_version: 2,
        max_score: 4,
        subtotal: assessment.subtotal,
        status: failed ? "ERROR" : "HISTORICAL_UNSCORED",
        summary: failed
          ? "Evaluation failed; findings require review."
          : "Archived observations with their available source evidence. These observations were not confirmed compliance findings.",
        criteria: assessment.criteria.map((criterion, index) => ({
          criterion_id: criterion.criterion_id,
          criterion_text: ITSO_CRITERION_NAMES[criterion.criterion_id],
          display_order: index,
          page_number:
            criterion.evidence
              .flatMap((fact) => fact.source_spans)
              .find((span) => span.page_number != null)?.page_number ?? null,
          score: failed ? null : criterion.score,
          justification: [
            ...new Set([
              ...criterion.evidence.map((fact) => fact.value),
              ...criterion.concerns,
              ...(criterion.score_withheld_reason
                ? [`Score withheld: ${criterion.score_withheld_reason}.`]
                : []),
              ...criterion.uncertainties,
            ]),
          ].join("\n\n"),
          evidence:
            [
              ...new Set(
                criterion.evidence.flatMap((fact) =>
                  fact.source_spans
                    .map((span) => span.quote)
                    .filter((quote): quote is string => Boolean(quote)),
                ),
              ),
            ].join("\n\n") || null,
        })),
      },
    },
  };
}
