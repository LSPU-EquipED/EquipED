import type { CriterionScoreItem } from "../types";

export interface CriterionScoreBucket {
  bucket: number;
  count: number;
}

export interface ScoreboardMetrics {
  attentionCount: number;
  strongCount: number;
  scoreBuckets: CriterionScoreBucket[];
  scoreBucketMax: number;
}

export function calculateScoreboardMetrics(
  criteria: CriterionScoreItem[],
): ScoreboardMetrics {
  let attentionCount = 0;
  let strongCount = 0;
  let count4 = 0;
  let count3 = 0;
  let count2 = 0;
  let count1 = 0;

  for (const criterion of criteria) {
    const score = criterion.score ?? 0;
    if (score < 3) {
      attentionCount += 1;
    } else {
      strongCount += 1;
    }

    const rounded = Math.round(score);
    if (rounded === 4) {
      count4 += 1;
    } else if (rounded === 3) {
      count3 += 1;
    } else if (rounded === 2) {
      count2 += 1;
    } else if (rounded === 1) {
      count1 += 1;
    }
  }

  const scoreBuckets = [
    { bucket: 4, count: count4 },
    { bucket: 3, count: count3 },
    { bucket: 2, count: count2 },
    { bucket: 1, count: count1 },
  ];
  const scoreBucketMax = Math.max(1, count4, count3, count2, count1);

  return {
    attentionCount,
    strongCount,
    scoreBuckets,
    scoreBucketMax,
  };
}

export type CriterionFilterType =
  | "ALL"
  | "ATTENTION"
  | "STRONG"
  | "CORRECTED"
  | 4
  | 3
  | 2
  | 1;

export function filterCriteria(
  criteria: CriterionScoreItem[],
  filter: CriterionFilterType,
): CriterionScoreItem[] {
  switch (filter) {
    case "ATTENTION":
      return criteria.filter((criterion) => (criterion.score ?? 0) < 3);
    case "STRONG":
      return criteria.filter((criterion) => (criterion.score ?? 0) >= 3);
    case "CORRECTED":
      return criteria.filter((criterion) =>
        Boolean(criterion.reviewer_correction),
      );
    case 4:
    case 3:
    case 2:
    case 1:
      return criteria.filter(
        (criterion) => Math.round(criterion.score ?? 0) === filter,
      );
    case "ALL":
    default:
      return criteria;
  }
}
