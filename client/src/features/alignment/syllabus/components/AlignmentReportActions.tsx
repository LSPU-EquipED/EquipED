import { useState } from 'react';
import { DownloadSimple } from '@phosphor-icons/react';
import { Button } from '@/shared/components/Button';
import type { AlignmentRun } from '../types';
import { exportAlignmentPdf } from '../utils/alignmentPdf';

export function AlignmentReportActions({
  run,
}: {
  run: AlignmentRun;
}) {
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const exportPdf = async () => {
    setExporting(true);
    setError(null);
    try {
      await exportAlignmentPdf(run);
    } catch {
      setError('The alignment PDF could not be created.');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center justify-end gap-2">
      <Button
        type="button"
        variant="secondary"
        size="sm"
        onClick={() => void exportPdf()}
        disabled={exporting}
        isLoading={exporting}
      >
        {!exporting ? <DownloadSimple className="size-4" /> : null}
        Export PDF
      </Button>
      {error && <p className="w-full text-right text-xs font-semibold text-destructive">{error}</p>}
    </div>
  );
}
