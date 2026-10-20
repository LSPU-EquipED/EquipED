import { ITSO_CRITERION_IDS, type ITSOAssessment } from "../itso";
export const hash = "a".repeat(64);
export function assessmentFixture(): ITSOAssessment {
  return {
    contract: "itso_evidence.v1",
    agent_name: "itso",
    evaluation_id: "evaluation-1",
    document_id: "document-1",
    source_hash: hash,
    raw_pdf_hash: hash,
    execution_status: "COMPLETED",
    scoring_complete: false,
    subtotal: null,
    error_code: null,
    revision: 0,
    effective_policy_hash: hash,
    source_snapshot_id: "snapshot-1",
    form_snapshot_id: "form-1",
    criteria: ITSO_CRITERION_IDS.map((criterion_id) => ({
      criterion_id,
      applicability: "unknown",
      applicability_reason: "Context requires authorized review",
      evidence_state: "observed",
      verification: "unverified",
      evidence: [
        {
          fact_id: `fact-${criterion_id}`,
          predicate: "candidate_context",
          value: "Proposed contextual observation",
          authority: "proposed_model",
          source_spans: [
            {
              source_id: "source-1",
              page_number: 2,
              start_offset: 10,
              end_offset: 24,
              text_hash: hash,
            },
          ],
          origin: "model",
          method_version: null,
          policy_version: null,
          reviewer_id: null,
          reviewed_at: null,
        },
      ],
      concerns: ["Proposed attribution concern"],
      uncertainties: ["Images and visual personal-data coverage are unknown."],
      score: null,
      score_withheld_reason:
        criterion_id === "ITSO-01"
          ? "authorized comparison corpus unavailable"
          : "approved active rule policy unavailable",
      rule_version: null,
    })),
  };
}
