export type {
  MatrixCriterionScoreItem,
  MatrixDomainScoreBlock,
  MatrixListResponse,
  MatrixMetrics,
  MonitoringMatrixRow,
} from '@equiped/types';

export interface SystemSummaryResponse {
  total_documents: number;
  total_faculty: number;
  active_evaluations: number;
  failed_evaluations: number;
}
