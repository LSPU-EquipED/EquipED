import { Download, Loader2 } from 'lucide-react';
import { useState } from 'react';
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
      <button
        type="button"
        onClick={() => void exportPdf()}
        disabled={exporting}
        className="inline-flex h-9 items-center gap-2 border border-slate-300 bg-white px-3 text-xs font-bold uppercase tracking-wide text-slate-700 disabled:opacity-50"
      >
        {exporting ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
        Export PDF
      </button>
      {error && <p className="w-full text-right text-xs font-semibold text-[#b91c1c]">{error}</p>}
    </div>
  );
}
