import type { ClientDocument } from "@equiped/types";
import type {
  DeskQueueItem,
  DomainScoreBlock,
  EvaluationResultsResponse,
  ExportDomainData,
} from "../types";

type EvaluationResultExportInput = {
  agentId: string;
  evaluationId: string;
  results: EvaluationResultsResponse;
  domainScore: DomainScoreBlock;
  criteria: DomainScoreBlock["criteria"];
  activeItem: Pick<DeskQueueItem, "title" | "program" | "course_code"> | null;
  activeDocument: ClientDocument | null;
};

export function buildEvaluationResultExport({
  agentId,
  evaluationId,
  results,
  domainScore,
  criteria,
  activeItem,
  activeDocument,
}: EvaluationResultExportInput): ExportDomainData {
  return {
    agentId,
    documentTitle:
      results.document_title ||
      activeItem?.title ||
      activeDocument?.title ||
      "Course Module",
    program:
      results.program || activeItem?.program || activeDocument?.program || null,
    courseCode: activeItem?.course_code || activeDocument?.courseCode || null,
    evaluationId,
    isPartial: results.is_partial,
    partialReason: results.partial_reason,
    evaluationStatus: results.evaluation_status,
    criteria,
    subtotal: domainScore.subtotal,
    max_score: domainScore.max_score || 4,
    status: domainScore.status || results.evaluation_status || "COMPLETED",
    adjectival_rating: domainScore.adjectival_rating ?? undefined,
    summary: domainScore.summary,
    version: domainScore.version,
    form_snapshot_id: domainScore.form_snapshot_id ?? undefined,
    results,
    document: activeDocument ?? null,
  };
}
