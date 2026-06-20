import { FileText, Download, Eye } from 'lucide-react';
import { useNavigate } from '@tanstack/react-router';
import type { ClientDocument } from '@/shared/types/documents';
import { Button } from '@/shared/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/shared/components/ui/sheet';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/tooltip';
import {
  GadExportDownloadButton,
  GadExportPreview,
  type ExportAgentId,
  type ExportDomainData,
} from './ExportDocument';
import type { EvaluationResultsResponse } from '../types';

type AgentDef = {
  id: ExportAgentId;
  name: string;
};

type EvaluationHeaderProps = {
  document: ClientDocument | null | undefined;
  selectedAgent: AgentDef;
  results: EvaluationResultsResponse | undefined;
  hasResults: boolean;
  isTerminal: boolean;
  evaluationId: string | null | undefined;
};

export function EvaluationHeader({
  document,
  selectedAgent,
  results,
  hasResults,
  isTerminal,
  evaluationId,
}: EvaluationHeaderProps) {
  const navigate = useNavigate();

  const domainScore = results?.domain_scores[selectedAgent.id];
  const domainData: ExportDomainData = {
    agentId: selectedAgent.id,
    documentTitle: document?.title || 'Unknown Document',
    program: document?.program ?? undefined,
    subtotal: domainScore?.subtotal || 0,
    max_score: domainScore?.max_score || 100,
    status: domainScore?.status || 'UNKNOWN',
    criteria: domainScore?.criteria || [],
  };

  const handleViewFullReport = () => {
    if (evaluationId) {
      void navigate({ to: '/evaluations/$id', params: { id: evaluationId } });
    }
  };

  return (
    <header className="flex min-h-24 shrink-0 items-center justify-between gap-4 border-b bg-background px-10">
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-[0.26em] text-muted-foreground">
          Selected Document
        </p>
        <h1 className="mt-2 truncate text-2xl font-semibold tracking-normal">
          {document?.title ?? 'Loading document...'}
        </h1>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <span className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm text-muted-foreground">
          <FileText className="size-4" aria-hidden="true" />
          {document?.pageCount != null ? `${document.pageCount} pages` : 'SLM'}
        </span>
        <Sheet>
          <SheetTrigger asChild>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  variant="outline"
                  className="gap-2"
                  disabled={!hasResults || !isTerminal}
                >
                  <Download className="size-4" aria-hidden="true" />
                  Export
                </Button>
              </TooltipTrigger>
              {(!hasResults || !isTerminal) && (
                <TooltipContent side="bottom">
                  {!isTerminal ? 'Available once evaluation completes' : 'No results to export'}
                </TooltipContent>
              )}
            </Tooltip>
          </SheetTrigger>
          <SheetContent className="!w-[52vw] !max-w-none gap-0 sm:!max-w-none">
            <SheetHeader className="border-b pr-14">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <SheetTitle>LSPU-CID-SF-004 {selectedAgent.name} Evaluation Export</SheetTitle>
                  <SheetDescription>
                    Preview follows the referenced Gender and Development Unit criteria form.
                  </SheetDescription>
                </div>
                <GadExportDownloadButton domainData={domainData} />
              </div>
            </SheetHeader>
            <div className="grid min-h-0 flex-1 place-items-start justify-items-center overflow-auto bg-muted/40 p-4 backdrop-blur-sm">
              <GadExportPreview domainData={domainData} />
            </div>
          </SheetContent>
        </Sheet>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              className="gap-2"
              disabled={!isTerminal || !evaluationId}
              onClick={handleViewFullReport}
            >
              <Eye className="size-4" aria-hidden="true" />
              View Full Report
            </Button>
          </TooltipTrigger>
          {!isTerminal && (
            <TooltipContent side="bottom">Available once evaluation completes</TooltipContent>
          )}
        </Tooltip>
      </div>
    </header>
  );
}
