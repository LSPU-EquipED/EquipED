import type { EvaluationResultsResponse } from "./evaluationResults";

export const ITSO_CRITERION_IDS = [
  "ITSO-01",
  "ITSO-02",
  "ITSO-03",
  "ITSO-04",
  "ITSO-05",
] as const;
export type ITSOCriterionId = (typeof ITSO_CRITERION_IDS)[number];
/** Presentation only; identifiers and institutional template rows remain unchanged. */
export const ITSO_CRITERION_NAMES: Record<ITSOCriterionId, string> = {
  "ITSO-01": "Intellectual property and attribution",
  "ITSO-02": "References and citations",
  "ITSO-03": "Faculty ownership",
  "ITSO-04": "Student confidentiality",
  "ITSO-05": "Teacher and student rights",
};
export interface ITSOSourceSpan {
  source_id: string;
  start_offset: number;
  end_offset: number;
  page_number: number | null;
  text_hash: string;
  quote?: string;
}
export interface ITSOEvidenceFact {
  fact_id: string;
  predicate: string;
  value: string;
  authority:
    | "proposed_model"
    | "verified_mechanical"
    | "confirmed_reviewer"
    | "rejected_reviewer"
    | "unresolved";
  source_spans: ITSOSourceSpan[];
  origin: string;
  method_version: string | null;
  policy_version: string | null;
  reviewer_id: string | null;
  reviewed_at: string | null;
}
export interface ITSOCriterionAssessment {
  criterion_id: ITSOCriterionId;
  applicability: "applicable" | "not_applicable" | "unknown";
  applicability_reason: string;
  evidence_state:
    | "observed"
    | "searched_no_match_with_coverage"
    | "none_supplied_or_located"
    | "incomplete"
    | "unavailable";
  verification:
    | "unverified"
    | "local_exact_match"
    | "local_near_match"
    | "provider_matched"
    | "provider_mismatched"
    | "provider_ambiguous"
    | "not_found_in_named_registry"
    | "unsupported_type"
    | "unavailable";
  evidence: ITSOEvidenceFact[];
  concerns: string[];
  uncertainties: string[];
  score: number | null;
  score_withheld_reason: string | null;
  rule_version: string | null;
}
/** Public reader intentionally has no packet, provider capture or generations fields. */
export interface ITSOAssessment {
  contract: "itso_evidence.v1";
  agent_name: "itso";
  evaluation_id: string;
  document_id: string;
  source_hash: string;
  raw_pdf_hash: string;
  execution_status: "COMPLETED" | "FAILED";
  scoring_complete: boolean;
  criteria: ITSOCriterionAssessment[];
  subtotal: number | null;
  error_code: string | null;
  revision: number;
  effective_policy_hash: string;
  source_snapshot_id: string;
  form_snapshot_id: string;
}
export interface LegacyAssessment {
  contract: "legacy.v1";
  result: EvaluationResultsResponse;
}
export interface AssessmentNotReady {
  detail: { code: "assessment_not_ready" };
}
export type EvaluationAssessment = ITSOAssessment | LegacyAssessment;
export type AssessmentRead = EvaluationAssessment | AssessmentNotReady;

const record = (v: unknown): v is Record<string, unknown> =>
  !!v && typeof v === "object" && !Array.isArray(v);
const strings = (v: unknown): v is string[] =>
  Array.isArray(v) && v.every((x) => typeof x === "string");
const digest = (v: unknown) =>
  typeof v === "string" && /^[a-f0-9]{64}$/.test(v);
const nullableString = (v: unknown) => v === null || typeof v === "string";
/** Fail closed at the public HTTP boundary rather than coerce v2 to a numeric legacy DTO. */
export function parseAssessment(value: unknown): AssessmentRead {
  if (!record(value)) throw new Error("Invalid assessment response.");
  if (record(value.detail) && value.detail.code === "assessment_not_ready")
    return { detail: { code: "assessment_not_ready" } };
  if (
    value.contract === "legacy.v1" &&
    record(value.result) &&
    record(value.result.domain_scores)
  )
    return value as unknown as LegacyAssessment;
  if (
    value.contract !== "itso_evidence.v1" ||
    "generations" in value ||
    "packets" in value ||
    value.agent_name !== "itso" ||
    !["COMPLETED", "FAILED"].includes(String(value.execution_status)) ||
    typeof value.scoring_complete !== "boolean" ||
    !Number.isInteger(value.revision) ||
    Number(value.revision) < 0 ||
    ![
      "evaluation_id",
      "document_id",
      "source_snapshot_id",
      "form_snapshot_id",
    ].every((k) => typeof value[k] === "string") ||
    !["source_hash", "raw_pdf_hash", "effective_policy_hash"].every((k) =>
      digest(value[k]),
    ) ||
    !Array.isArray(value.criteria) ||
    value.criteria.length !== 5
  )
    throw new Error("Unsupported assessment response.");
  for (const [index, c] of value.criteria.entries()) {
    if (
      !record(c) ||
      c.criterion_id !== ITSO_CRITERION_IDS[index] ||
      !["applicable", "not_applicable", "unknown"].includes(
        String(c.applicability),
      ) ||
      typeof c.applicability_reason !== "string" ||
      ![
        "observed",
        "searched_no_match_with_coverage",
        "none_supplied_or_located",
        "incomplete",
        "unavailable",
      ].includes(String(c.evidence_state)) ||
      ![
        "unverified",
        "local_exact_match",
        "local_near_match",
        "provider_matched",
        "provider_mismatched",
        "provider_ambiguous",
        "not_found_in_named_registry",
        "unsupported_type",
        "unavailable",
      ].includes(String(c.verification)) ||
      !strings(c.concerns) ||
      !strings(c.uncertainties) ||
      !Array.isArray(c.evidence) ||
      !nullableString(c.rule_version) ||
      !nullableString(c.score_withheld_reason) ||
      !(c.score === null
        ? !!c.score_withheld_reason
        : Number.isInteger(c.score) &&
          Number(c.score) >= 1 &&
          Number(c.score) <= 4 &&
          !!c.rule_version &&
          !c.score_withheld_reason)
    )
      throw new Error("Invalid assessment criterion.");
    for (const f of c.evidence) {
      if (
        !record(f) ||
        !["fact_id", "predicate", "value", "origin"].every(
          (k) => typeof f[k] === "string",
        ) ||
        ![
          "proposed_model",
          "verified_mechanical",
          "confirmed_reviewer",
          "rejected_reviewer",
          "unresolved",
        ].includes(String(f.authority)) ||
        ![
          "method_version",
          "policy_version",
          "reviewer_id",
          "reviewed_at",
        ].every((k) => nullableString(f[k])) ||
        !Array.isArray(f.source_spans)
      )
        throw new Error("Invalid assessment fact.");
      if (
        (f.authority === "confirmed_reviewer" ||
          f.authority === "rejected_reviewer") &&
        (!f.reviewer_id || !f.reviewed_at || !f.policy_version)
      )
        throw new Error("Missing reviewer provenance.");
      if (
        f.authority === "verified_mechanical" &&
        ![
          "exact-title.v1",
          "exact-author.v1",
          "exact-year.v1",
          "citation-link.v1",
          "hash-offset.v1",
        ].includes(String(f.method_version))
      )
        throw new Error("Unsupported mechanical method.");
      for (const span of f.source_spans) {
        if (
          !record(span) ||
          typeof span.source_id !== "string" ||
          !digest(span.text_hash) ||
          !Number.isInteger(span.start_offset) ||
          Number(span.start_offset) < 0 ||
          !Number.isInteger(span.end_offset) ||
          Number(span.end_offset) <= Number(span.start_offset) ||
          !(
            span.page_number === null ||
            (Number.isInteger(span.page_number) &&
              Number(span.page_number) >= 1)
          )
        )
          throw new Error("Invalid evidence location.");
      }
    }
  }
  const criteria = value.criteria as unknown as ITSOCriterionAssessment[];
  const complete = criteria.every((c) => c.score !== null);
  const expected = complete
    ? criteria.reduce((sum, c) => sum + c.score!, 0) / 5
    : null;
  if (
    value.scoring_complete !== complete ||
    value.subtotal !== expected ||
    !nullableString(value.error_code) ||
    (value.execution_status === "FAILED" && !value.error_code)
  )
    throw new Error("Inconsistent assessment status.");
  return value as unknown as ITSOAssessment;
}
