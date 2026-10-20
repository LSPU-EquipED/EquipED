import type { CriterionScoreItem } from "../types";
import { cleanJustification, formatEvidenceText } from "./scoreHelpers";

// Historical results may use presentation aliases alongside the saved criterion fields.
type PresentedCriterion = CriterionScoreItem & {
  code?: string;
  criterion?: string;
  page_number?: number | string | null;
};

export function getCriterionPresentation(criterion: PresentedCriterion) {
  return {
    code: criterion.code || criterion.criterion_id,
    pageNumber: criterion.page_number,
    criterionText:
      criterion.criterion_text || criterion.criterion || criterion.description,
  };
}

// Missing quotations describe the saved evidence, not absence from the whole SLM.
export function getAdvisoryEvidenceStatus(criterion: PresentedCriterion) {
  if (
    formatEvidenceText(criterion.evidence) ||
    !cleanJustification(criterion.justification)
  )
    return null;
  const { code } = getCriterionPresentation(criterion);
  if (
    code === "ITSO-04" &&
    criterion.score === 4 &&
    criterion.evidence_status === "no_concern_detected"
  )
    return "no_concern_detected";
  if (
    code === "ITSO-05" &&
    criterion.score === 3 &&
    criterion.evidence_status === "rights_unverified"
  )
    return "rights_unverified";
  return null;
}

export function getMissingEvidenceNote(
  criterion: PresentedCriterion,
): string | null {
  if (formatEvidenceText(criterion.evidence)) return null;
  const status = getAdvisoryEvidenceStatus(criterion);
  if (status === "no_concern_detected")
    return "No confidentiality concern was detected in the reviewed text; there is no passage to quote.";
  if (status === "rights_unverified")
    return "Rights and permissions remain unverified from the reviewed text. This score is provisional.";
  const { code } = getCriterionPresentation(criterion);
  if (code === "ITSO-04") {
    return "No SLM quotation was recorded for the confidentiality check. This does not confirm that the entire module is clear.";
  }
  if (code === "ITSO-05") {
    return "No SLM quotation establishes teacher/student permissions or protections. Confirm these provisions during review.";
  }
  return "No quoted evidence was returned.";
}

export function summarizeITSODocumentEvidence(
  criteria: readonly PresentedCriterion[],
) {
  const unquotedCodes: string[] = [];
  let hasNoConfidentialityConcern = false;
  let hasUnverifiedRights = false;
  for (const criterion of criteria) {
    const status = getAdvisoryEvidenceStatus(criterion);
    const { code } = getCriterionPresentation(criterion);
    if (status === "no_concern_detected") hasNoConfidentialityConcern = true;
    if (status === "rights_unverified") hasUnverifiedRights = true;
    if (
      code.startsWith("ITSO-") &&
      !status &&
      !formatEvidenceText(criterion.evidence)
    ) {
      unquotedCodes.push(code);
    }
  }
  return { unquotedCodes, hasNoConfidentialityConcern, hasUnverifiedRights };
}
