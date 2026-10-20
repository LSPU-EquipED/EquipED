import { describe, expect, it } from "vitest";
import { parseAssessment } from "../itso";
import { assessmentFixture } from "./itso.fixture";

describe("public assessment boundary", () => {
  it("accepts five ordered nullable criteria without inventing a legacy score", () => {
    const value = assessmentFixture();
    expect(parseAssessment(value)).toEqual(value);
    expect("generations" in value).toBe(false);
  });
  it("keeps pending projection distinct from an assessment", () => {
    expect(
      parseAssessment({ detail: { code: "assessment_not_ready" } }),
    ).toEqual({ detail: { code: "assessment_not_ready" } });
  });
  it("preserves legacy response under its discriminator", () => {
    const result = { domain_scores: { itso: { subtotal: 3 } } };
    expect(parseAssessment({ contract: "legacy.v1", result })).toEqual({
      contract: "legacy.v1",
      result,
    });
  });
  it.each([
    ["generations", { generations: [] }],
    ["missing row", { criteria: assessmentFixture().criteria.slice(0, 4) }],
    ["zero-filled subtotal", { subtotal: 0 }],
    ["false scoring completeness", { scoring_complete: true }],
    ["failed without error", { execution_status: "FAILED" }],
  ])("rejects %s", (_label, patch) =>
    expect(() =>
      parseAssessment({ ...assessmentFixture(), ...patch }),
    ).toThrow(),
  );
  it("rejects malformed locations and model-forged authority", () => {
    const v = assessmentFixture();
    v.criteria[0].evidence[0].source_spans[0].end_offset = 2;
    expect(() => parseAssessment(v)).toThrow();
    const forged = assessmentFixture();
    Object.assign(forged.criteria[0].evidence[0], {
      authority: "institutional_approval",
    });
    expect(() => parseAssessment(forged)).toThrow();
  });
});
