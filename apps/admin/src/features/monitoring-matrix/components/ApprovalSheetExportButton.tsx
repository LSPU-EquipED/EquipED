import { useState } from 'react';
import { Printer, SpinnerGap } from '@phosphor-icons/react';
import { Button } from '@equiped/ui';
import type { MasterSynthesisDetailResponse } from '../types';
import { downloadApprovalSheetPdf } from '../utils/approvalSheetPdf';

export function ApprovalSheetExportButton({ data }: { data: MasterSynthesisDetailResponse }) {
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const handleExport = async () => {
    if (isExporting) return;
    setIsExporting(true);
    setError(null);
    try {
      await downloadApprovalSheetPdf(data);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'PDF export failed. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };
  return (
    <div className="flex max-w-xs flex-col items-end gap-2">
      <Button type="button" variant="outline" size="sm" onClick={handleExport}
        disabled={isExporting} aria-busy={isExporting}
        className="h-9 gap-1.5 text-xs font-semibold" data-testid="export-pdf-button"
        aria-label={isExporting ? 'Creating approval sheet PDF' : 'Export PDF'}>
        {isExporting
          ? <SpinnerGap className="size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
          : <Printer className="size-4" aria-hidden="true" />}
        <span className="hidden sm:inline">{isExporting ? 'Creating PDF…' : 'Export PDF'}</span>
      </Button>
      {error ? <p role="alert" className="text-right text-xs text-destructive">{error}</p> : null}
    </div>
  );
}
