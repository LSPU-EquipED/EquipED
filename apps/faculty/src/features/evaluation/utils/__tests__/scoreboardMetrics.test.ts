import { describe, expect, it } from "vitest";
import { formatDateWithFallback } from "../dateFormatting";
import {
  calculateScoreboardMetrics,
  filterCriteria,
} from "../scoreboardMetrics";
import type { CriterionScoreItem } from "../../types";

describe("dateFormatting", () => {
  it("returns fallback when date string is undefined, null, or empty", () => {
    expect(formatDateWithFallback(undefined)).toBe("Not recorded");
    expect(formatDateWithFallback(null)).toBe("Not recorded");
    expect(formatDateWithFallback("")).toBe("Not recorded");
    expect(formatDateWithFallback(undefined, "Not specified")).toBe(
      "Not specified",
    );
    expect(formatDateWithFallback(null, "Recent")).toBe("Recent");
  });

  it("returns fallback when date string is invalid", () => {
    expect(formatDateWithFallback("not-a-date")).toBe("Not recorded");
    expect(formatDateWithFallback("invalid", "Recent")).toBe("Recent");
  });

  it("formats valid ISO date string correctly in en-US format", () => {
    const formatted = formatDateWithFallback("2025-01-15T00:00:00Z");
    expect(formatted).toBe("Jan 15, 2025");
  });
});

describe("scoreboardMetrics", () => {
  const sampleCriteria: CriterionScoreItem[] = [
    {
      criterion_id: "C1",
      criterion_text: "Criterion 1",
      score: 4,
      justification: "Excellent",
    },
    {
      criterion_id: "C2",
      criterion_text: "Criterion 2",
      score: 3.2,
      justification: "Good",
    },
    {
      criterion_id: "C3",
      criterion_text: "Criterion 3",
      score: 2.1,
      justification: "Needs improvement",
      reviewer_correction: {
        action: "EDIT",
        score: 3,
        justification: "Overridden",
      },
    },
    {
      criterion_id: "C4",
      criterion_text: "Criterion 4",
      score: 1,
      justification: "Poor",
    },
    {
      criterion_id: "C5",
      criterion_text: "Criterion 5",
      score: 3.7,
      justification: "Very good",
    },
  ];

  it("calculates attentionCount, strongCount, scoreBuckets, and scoreBucketMax accurately", () => {
    const metrics = calculateScoreboardMetrics(sampleCriteria);

    // Attention: score < 3 -> C3 (2.1), C4 (1) -> 2
    expect(metrics.attentionCount).toBe(2);
    // Strong: length - attentionCount = 5 - 2 = 3
    expect(metrics.strongCount).toBe(3);

    // Rounded buckets:
    // C1: 4 -> bucket 4
    // C2: Math.round(3.2) = 3 -> bucket 3
    // C3: Math.round(2.1) = 2 -> bucket 2
    // C4: Math.round(1) = 1 -> bucket 1
    // C5: Math.round(3.7) = 4 -> bucket 4
    // Bucket 4: 2, Bucket 3: 1, Bucket 2: 1, Bucket 1: 1
    expect(metrics.scoreBuckets).toEqual([
      { bucket: 4, count: 2 },
      { bucket: 3, count: 1 },
      { bucket: 2, count: 1 },
      { bucket: 1, count: 1 },
    ]);
    expect(metrics.scoreBucketMax).toBe(2);
  });

  it("handles empty criteria list cleanly", () => {
    const metrics = calculateScoreboardMetrics([]);
    expect(metrics.attentionCount).toBe(0);
    expect(metrics.strongCount).toBe(0);
    expect(metrics.scoreBuckets).toEqual([
      { bucket: 4, count: 0 },
      { bucket: 3, count: 0 },
      { bucket: 2, count: 0 },
      { bucket: 1, count: 0 },
    ]);
    expect(metrics.scoreBucketMax).toBe(1);
  });

  describe("filterCriteria", () => {
    it("filters by ALL", () => {
      expect(filterCriteria(sampleCriteria, "ALL")).toHaveLength(5);
    });

    it("filters by ATTENTION (< 3)", () => {
      const filtered = filterCriteria(sampleCriteria, "ATTENTION");
      expect(filtered.map((c) => c.criterion_id)).toEqual(["C3", "C4"]);
    });

    it("filters by STRONG (>= 3)", () => {
      const filtered = filterCriteria(sampleCriteria, "STRONG");
      expect(filtered.map((c) => c.criterion_id)).toEqual(["C1", "C2", "C5"]);
    });

    it("filters by CORRECTED", () => {
      const filtered = filterCriteria(sampleCriteria, "CORRECTED");
      expect(filtered.map((c) => c.criterion_id)).toEqual(["C3"]);
    });

    it("filters by exact rounded bucket number", () => {
      expect(filterCriteria(sampleCriteria, 4).map((c) => c.criterion_id)).toEqual([
        "C1",
        "C5",
      ]);
      expect(filterCriteria(sampleCriteria, 3).map((c) => c.criterion_id)).toEqual([
        "C2",
      ]);
      expect(filterCriteria(sampleCriteria, 2).map((c) => c.criterion_id)).toEqual([
        "C3",
      ]);
      expect(filterCriteria(sampleCriteria, 1).map((c) => c.criterion_id)).toEqual([
        "C4",
      ]);
    });
  });
});
