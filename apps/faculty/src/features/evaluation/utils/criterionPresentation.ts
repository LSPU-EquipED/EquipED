import type { CriterionScoreItem } from "../types";

// Historical results may use presentation aliases alongside the saved criterion fields.
type PresentedCriterion = CriterionScoreItem & {
  code?: string;
  criterion?: string;
  page_number?: number | string;
};

export function getCriterionPresentation(criterion: PresentedCriterion) {
  return {
    code: criterion.code || criterion.criterion_id,
    pageNumber: criterion.page_number,
    criterionText:
      criterion.criterion_text || criterion.criterion || criterion.description,
  };
}
