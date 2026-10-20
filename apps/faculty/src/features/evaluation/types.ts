import type {
  EvaluationResultsResponse,
  CriterionScoreItem,
} from "@equiped/types";
export type {
  CriterionReviewerCorrection,
  EvaluationFormCriterionPresentation,
  EvaluationFormDomainPresentation,
  EvaluationFormPresentation,
  RawMeasurementItem,
  CriterionScoreItem,
  DomainScoreBlock,
  EvaluationFlagItem,
  EvaluationResultsResponse,
} from "@equiped/types";
import type {
  ClientDocument,
  TargetAgent,
  EvaluationListItem,
  EvaluationListResponse,
  EvaluationListStats,
} from "@equiped/types";

export type {
  TargetAgent,
  EvaluationListItem,
  EvaluationListResponse,
  EvaluationListStats,
};

export type TargetAgentOrLegacy = TargetAgent | "all";

export type EvaluationStatus =
  | "SUBMITTED"
  | "PREPROCESSING"
  | "EVALUATING"
  | "SYNTHESIZING"
  | "COMPLETED"
  | "FAILED";

export interface EvaluationSubmitRequest {
  document_id: string;
  syllabus_id?: string | null;
  curriculum_id?: string | null;
  /** Target specialist agent for this evaluation job. Required. */
  target_agent: TargetAgent;
  confirmed_program?: string | null;
  /**
   * Retained for backend compatibility: the API still accepts and returns
   * this field (defaulting to false). New submissions always send false.
   */
  partial_without_curriculum?: boolean;
}

export type CriterionReviewDraft = {
  score: number;
  justification: string;
  rejected: boolean;
  expanded: boolean;
  /** Whether the "what counted toward this score" checklist is open. */
  itemsExpanded: boolean;
  /** item_id -> locally rejected? Only populated for criteria with raw_items. */
  itemRejections: Record<string, boolean>;
};

export interface EvaluationResponse {
  evaluation_id: string;
  document_id: string;
  syllabus_id?: string | null;
  curriculum_id?: string | null;
  /** Target specialist agent. Legacy bundle jobs report 'all'. */
  target_agent?: TargetAgentOrLegacy;
  status: EvaluationStatus;
  error_message?: string;
  partial_without_curriculum?: boolean;
  partial_reason?: string | null;
  submitted_by?: string;
  submitted_at: string;
  completed_at?: string;
  duration_seconds?: number | null;
}

export interface EvaluationStatusResponse {
  evaluation_id: string;
  status: EvaluationStatus;
  /** Target specialist agent. Legacy bundle jobs report 'all'. */
  target_agent?: TargetAgentOrLegacy;
  error_message?: string;
  partial_without_curriculum?: boolean;
  partial_reason?: string | null;
  completed_at?: string;
  duration_seconds?: number | null;
}

export type DeskQueueStatus = "READY" | "EVALUATING" | "COMPLETED" | "FAILED";

export interface DeskQueueItem {
  document_id: string;
  title: string;
  course_code: string | null;
  program: string | null;
  uploaded_at: string;
  my_status: DeskQueueStatus | string;
  my_score: number | null;
  my_adjectival: string | null;
  peer_completed_count: number;
  peer_completed_desks: string[];
}

export interface DeskQueueListResponse {
  items: DeskQueueItem[];
  total: number;
}

export type CriterionFeedbackAction =
  "ACCEPT" | "REJECT" | "EDIT" | "ITEM_REJECT" | "ITEM_ACCEPT";

export interface CriterionFeedbackRequest {
  agent_name: string;
  action: CriterionFeedbackAction;
  score?: number;
  justification?: string;
  notes?: string;
  item_id?: string;
}

export interface CriterionFeedbackResponse {
  log_id: string;
  evaluation_id: string;
  user_id: string;
  agent_name: string | null;
  criterion_id: string | null;
  item_id?: string | null;
  action: CriterionFeedbackAction;
  edited_json: { score: number; justification: string } | null;
  notes: string | null;
  created_at: string;
}

export type ExportAgentId = "coordinator" | "sme" | "gad" | "itso";

// Minimal domain block used by the per-agent export. The page that owns
// the export builds this block from the full evaluation result. The metadata
// loader fills known document and faculty details before download; unresolved
// values remain blank.
export type ExportDomainData = {
  agentId: ExportAgentId | string;
  documentTitle?: string;
  program?: string | null;
  courseTitle?: string | null;
  courseCode?: string | null;
  academicYear?: string | null;
  semester?: string | null;
  // Human evaluator's printed name; never an automated agent or signature.
  reviewer?: string | null;
  evaluatedAt?: string | null;
  facultyName?: string | null;
  college?: string | null;
  evaluationId?: string;
  isPartial?: boolean;
  partialReason?: string | null;
  evaluationStatus?: string;
  criteria: ReadonlyArray<CriterionScoreItem>;
  subtotal: number | null;
  max_score: number;
  status: string;
  adjectival_rating?: string;
  summary?: string;
  version?: number | null;
  form_snapshot_id?: string | null;
  legacy_notice?: string | null;
  // Carries the saved evaluation state, document ID and completion timestamp
  // so the export uses the same evaluation record as the scorecard.
  results?: EvaluationResultsResponse;
  document?: ClientDocument | null;
};
