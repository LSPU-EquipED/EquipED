import { describe, expect, it } from "vitest";
import { assessmentFixture } from "../../../../../../../libs/types/src/__tests__/itso.fixture";
import { historicalITSOResults } from "../historicalITSOResults";

describe("historical ITSO presentation in the existing scorecard", () => {
  it("preserves unavailable scores and exact source excerpts without technical identifiers", () => {
    const assessment = assessmentFixture();
    const fact = assessment.criteria[0].evidence[0];
    fact.source_spans[0].quote = "Exact frozen source wording.";
    const result = historicalITSOResults(assessment);
    expect(result.overall_score).toBeNull();
    expect(result.synthesized_score).toBeNull();
    expect(result.domain_scores.itso.subtotal).toBeNull();
    expect(result.domain_scores.itso.criteria[0].score).toBeNull();
    expect(result.domain_scores.itso.criteria[0].evidence).toBe(
      "Exact frozen source wording.",
    );
    expect(result.domain_scores.itso.criteria[0].justification).not.toContain(
      fact.source_spans[0].source_id,
    );
  });
  it("preserves failed execution rather than presenting an archived successful review", () => {
    const assessment = assessmentFixture();
    assessment.execution_status = "FAILED";
    const result = historicalITSOResults(assessment);
    expect(result.evaluation_status).toBe("FAILED");
    expect(result.domain_scores.itso.status).toBe("ERROR");
    expect(result.failed_agents).toEqual(["itso"]);
    expect(
      result.domain_scores.itso.criteria.every(
        (criterion) => criterion.score === null,
      ),
    ).toBe(true);
  });
});
