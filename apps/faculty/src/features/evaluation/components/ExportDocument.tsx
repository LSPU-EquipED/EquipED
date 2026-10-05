import { useState } from 'react';
import { DownloadSimple } from '@phosphor-icons/react';
import { Button, cn } from '@equiped/ui';
import { TARGET_AGENT_META, isTargetAgent } from '@equiped/types';
import type { ExportAgentId, ExportDomainData } from '../types';
import { CANONICAL_MAX_SCORE } from '../utils/scoreHelpers';
import { downloadSpecialistPdf } from '../utils/specialistPdf';
import { loadSpecialistPdfMetadata } from '../utils/specialistPdfMetadata';

export type { ExportAgentId, ExportDomainData } from '../types';

type ExportDocumentProps = {
  readonly domainData?: ExportDomainData;
  readonly agentId?: ExportAgentId;
};

function getExportDomainData({
  domainData,
  agentId = 'gad',
}: ExportDocumentProps): ExportDomainData {
  return (
    domainData ?? {
      agentId,
      criteria: [],
      subtotal: 0,
      max_score: CANONICAL_MAX_SCORE,
      status: 'PENDING',
    }
  );
}

export function SpecialistExportDownloadButton({
  domainData: explicitDomainData,
  agentId,
  className,
  variant = 'secondary',
}: ExportDocumentProps & { className?: string; variant?: 'primary' | 'secondary' | 'outline' }) {
  const domainData = getExportDomainData({ domainData: explicitDomainData, agentId });
  const [isDownloading, setIsDownloading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleDownload = async () => {
    setIsDownloading(true);
    setErrorMessage(null);
    try {
      await downloadSpecialistPdf(await loadSpecialistPdfMetadata(domainData));
    } catch (error) {
      console.error('Unable to create the per-agent evaluation PDF.', error);
      setErrorMessage('PDF export failed. Please try again.');
    } finally {
      setIsDownloading(false);
    }
  };

  const safeAgentId = String(domainData.agentId).toLowerCase();
  const agentLabel = isTargetAgent(safeAgentId)
    ? TARGET_AGENT_META[safeAgentId].shortLabel
    : safeAgentId.toUpperCase();

  return (
    <div className="inline-flex flex-col items-start gap-1">
      <Button
        type="button"
        variant={variant}
        size="sm"
        aria-label={`Download PDF - ${agentLabel} Scorecard`}
        className={cn('gap-1.5 font-semibold text-xs h-8.5 px-3', className)}
        onClick={handleDownload}
        disabled={isDownloading}
      >
        <DownloadSimple className="size-3.5" aria-hidden="true" />
        <span>{isDownloading ? 'Creating PDF…' : `Download ${agentLabel} PDF`}</span>
      </Button>
      {errorMessage && (
        <span className="text-xs font-medium text-destructive" role="alert">
          {errorMessage}
        </span>
      )}
    </div>
  );
}

export const GadExportDownloadButton = SpecialistExportDownloadButton;
