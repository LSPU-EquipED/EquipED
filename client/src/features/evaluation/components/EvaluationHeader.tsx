import { Clock, FileText, Download, Eye, AlertTriangle } from 'lucide-react';
import { useNavigate } from '@tanstack/react-router';
import { useState } from 'react';
import type { ClientDocument } from '@/shared/types/documents';
import {
  GadExportDownloadButton,
  GadExportPreview,
  type ExportAgentId,
  type ExportDomainData,
} from './ExportDocument';
import type { EvaluationResultsResponse, EvaluationStatusResponse } from '../types';

function formatDuration(seconds?: number | null): string {
  if (seconds == null) return '';
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m ${secs}s`;
}

type AgentDef = {
  id: ExportAgentId;
  name: string;
};

type EvaluationHeaderProps = {
  document: ClientDocument | null | undefined;
  selectedAgent: AgentDef;
  results: EvaluationResultsResponse | undefined;
  status: EvaluationStatusResponse | undefined;
  hasResults: boolean;
  isTerminal: boolean;
  evaluationId: string | null | undefined;
};

export function EvaluationHeader({
  document,
  selectedAgent,
  results,
  status,
  hasResults,
  isTerminal,
  evaluationId,
}: EvaluationHeaderProps) {
  const navigate = useNavigate();
  const [showExportModal, setShowExportModal] = useState(false);

  const isPartial = Boolean(results?.is_partial || status?.partial_without_curriculum);
  const partialReason = results?.partial_reason || status?.partial_reason;

  const domainScore = results?.domain_scores[selectedAgent.id];
  // The persisted `EvaluationResponse` carries `submitted_by`; the
  // `EvaluationResultsResponse` does not, so we leave the reviewer
  // unavailable rather than invent a name.
  const reviewer = null;
  const domainData: ExportDomainData = {
    agentId: selectedAgent.id,
    documentTitle: document?.title ?? undefined,
    program: document?.program ?? null,
    courseTitle: document?.courseTitle ?? null,
    courseCode: document?.courseCode ?? null,
    academicYear: document?.academicYear ?? null,
    reviewer,
    evaluationId: evaluationId ?? undefined,
    isPartial,
    partialReason: partialReason ?? null,
    evaluationStatus: results?.evaluation_status,
    subtotal: domainScore?.subtotal || 0,
    max_score: domainScore?.max_score || 4,
    status: domainScore?.status || 'UNKNOWN',
    adjectival_rating: domainScore?.adjectival_rating ?? undefined,
    criteria: domainScore?.criteria || [],
    summary: domainScore?.summary,
    version: domainScore?.version,
    form_snapshot_id: domainScore?.form_snapshot_id,
    legacy_notice: results?.legacy_notice,
    results,
    document: document ?? null,
  };

  const handleViewFullReport = () => {
    if (evaluationId) {
      void navigate({ to: '/evaluations/$id', params: { id: evaluationId } });
    }
  };

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-slate-200 bg-white px-6">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <h1
          className="truncate text-sm font-bold tracking-tight text-slate-900"
          title={document?.title ?? ''}
        >
          {document?.title ?? 'Loading document...'}
        </h1>

        <span className="inline-flex shrink-0 items-center gap-1.5 rounded-sm border border-slate-200 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-600 bg-slate-50 select-none">
          <FileText className="size-3 text-slate-400" aria-hidden="true" />
          {document?.pageCount != null ? `${document.pageCount} pages` : 'SLM'}
        </span>

        {isTerminal && hasResults && results?.duration_seconds != null && (
          <span
            className="inline-flex shrink-0 items-center gap-1 font-mono text-[10px] font-semibold tabular-nums text-slate-600 bg-slate-50 border border-slate-200 px-2 py-0.5 rounded-sm select-none"
            title="Evaluation duration"
          >
            <Clock className="size-3 text-slate-400" aria-hidden="true" />
            {formatDuration(results.duration_seconds)}
          </span>
        )}

        {isPartial && (
          <span className="inline-flex shrink-0 items-center gap-1.5 rounded-sm border border-[#f2c811]/40 bg-[#f2c811]/5 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[#1e293b] select-none">
            <AlertTriangle className="size-3 text-[#f2c811]" aria-hidden="true" />
            Partial Review
          </span>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <button
          type="button"
          className="inline-flex h-8 items-center justify-center border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 px-3 rounded-sm text-xs font-bold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87] disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none cursor-pointer"
          disabled={!hasResults || !isTerminal}
          onClick={() => setShowExportModal(true)}
          title={
            !hasResults || !isTerminal
              ? !isTerminal
                ? 'Available once evaluation completes'
                : 'No results to export'
              : undefined
          }
        >
          <Download className="size-3.5 mr-1.5" aria-hidden="true" />
          Export
        </button>

        <button
          type="button"
          className="inline-flex h-8 items-center justify-center bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-white px-3 rounded-sm text-xs font-bold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87] disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none cursor-pointer"
          disabled={!isTerminal || !evaluationId}
          onClick={handleViewFullReport}
          title={!isTerminal ? 'Available once evaluation completes' : undefined}
        >
          <Eye className="size-3.5 mr-1.5" aria-hidden="true" />
          Full Report
        </button>

        {showExportModal && (
          <div
            className="fixed inset-0 z-50 flex justify-end bg-slate-900/40"
            onClick={() => setShowExportModal(false)}
          >
            <div
              className="w-full max-w-4xl bg-white border-l border-slate-200 h-full flex flex-col justify-between overflow-hidden relative"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex flex-col h-full">
                <div className="border-b border-slate-200 p-6 bg-slate-50/50">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <h3 className="text-base font-bold text-slate-900 uppercase tracking-wider">
                        LSPU-CID-SF-004 {selectedAgent.name} Evaluation Export
                        {isPartial && ' — Partial'}
                      </h3>
                      <p className="mt-1 text-xs font-semibold text-slate-500 uppercase tracking-wider leading-relaxed">
                        Preview follows the referenced Gender and Development Unit criteria form.
                        {isPartial && partialReason
                          ? ` ${partialReason}`
                          : isPartial
                            ? ' This evaluation ran without a curriculum reference; Coordinator review was skipped.'
                            : ''}
                      </p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <GadExportDownloadButton domainData={domainData} />
                      <button
                        type="button"
                        onClick={() => setShowExportModal(false)}
                        className="inline-flex h-9 items-center justify-center border border-slate-200 hover:bg-slate-50 text-slate-700 px-3.5 rounded-sm text-xs font-semibold tracking-wide uppercase focus:outline-none transition-colors"
                      >
                        Close
                      </button>
                    </div>
                  </div>
                </div>
                <div className="grid min-h-0 flex-1 place-items-start justify-items-center overflow-auto bg-slate-50/20 p-6">
                  <GadExportPreview domainData={domainData} />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
