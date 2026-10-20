import type { CoordinatorAlignmentAdvisory } from "./evaluations";

export type CriterionReviewerCorrection = {
  action: "EDIT" | "REJECT";
  score: number | null;
  justification: string | null;
};

export interface EvaluationFormCriterionPresentation {
  rubric_criterion_id: string;
  criterion_code: string;
  title: string;
  description: string;
  display_order: number;
}

export interface EvaluationFormDomainPresentation {
  rubric_domain_id: string;
  code: string;
  title: string;
  display_order: number;
  criteria: EvaluationFormCriterionPresentation[];
}

export interface EvaluationFormPresentation {
  form_snapshot_id: string;
  rubric_set_id: string;
  version: number;
  snapshot_hash: string;
  adapter_key: string;
  adapter_version: number;
  domains: EvaluationFormDomainPresentation[];
}

export interface RawMeasurementItem {
  item_id: string;
  text: string;
  included: boolean;
  rejected: boolean;
}

export interface ITSOResultPublicSource {
  number: number;
  title?: string | null;
  url: string;
  excerpt: string;
}

export interface CriterionScoreItem {
  rubric_criterion_id?: string | null;
  criterion_id: string;
  criterion_text: string;
  description?: string | null;
  display_order?: number | null;
  page_number?: number | string | null;
  score: number | null;
  justification: string;
  evidence?: string | null;
  is_ungrounded?: boolean;
  evidence_status?: "no_concern_detected" | "rights_unverified" | null;
  public_sources?: ITSOResultPublicSource[];
  reference_check_note?: string | null;
  reviewer_correction?: CriterionReviewerCorrection | null;
  raw_items?: RawMeasurementItem[] | null;
  corrected_score?: number | null;
}

export interface DomainScoreBlock {
  advisory_outputs?: CoordinatorAlignmentAdvisory | null;
  form_snapshot_id?: string | null;
  rubric_set_id?: string | null;
  version?: number | null;
  snapshot_hash?: string | null;
  adapter_key?: string | null;
  adapter_version?: number | null;
  domain_id?: string | null;
  domain_name?: string | null;
  domain_display_order?: number | null;
  criteria: CriterionScoreItem[];
  subtotal: number | null;
  max_score: number;
  status: string;
  adjectival_rating?: string | null;
  summary?: string;
}

export interface EvaluationFlagItem {
  flag_id: string;
  evaluation_id: string;
  agent_id: string;
  criterion_id: string;
  criterion_text: string;
  score: number;
  justification?: string;
  chunk_id?: string;
}

export interface EvaluationResultsResponse {
  evaluation_id: string;
  document_id: string;
  syllabus_id?: string | null;
  document_title?: string | null;
  program?: string | null;
  synthesized_score: number | null;
  overall_score?: number | null;
  adjectival_rating?: string | null;
  domain_scores: Record<string, DomainScoreBlock>;
  flags: EvaluationFlagItem[];
  active_agents: string[];
  failed_agents: string[];
  is_partial: boolean;
  partial_reason?: string | null;
  evaluation_status: string;
  submitted_at?: string | null;
  completed_at?: string | null;
  duration_seconds?: number | null;
  forms?: Record<string, EvaluationFormPresentation>;
  legacy_notice?: string | null;
}
