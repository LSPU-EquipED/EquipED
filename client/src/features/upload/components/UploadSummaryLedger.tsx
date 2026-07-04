import { CheckCircle, XCircle } from 'lucide-react';
import { cn } from '@/shared/components/utils';
import type { DocumentUploadResponse } from '@/shared/types/documents';

interface UploadSummaryLedgerProps {
  uploadResult: DocumentUploadResponse | null;
  isSuccess: boolean;
  isFailed: boolean;
  file: File | null;
  sourceTypeLabels: Record<string, string>;
  sourceType: string;
}

export function UploadSummaryLedger({
  uploadResult,
  isSuccess,
  isFailed,
  file,
  sourceTypeLabels,
  sourceType,
}: UploadSummaryLedgerProps) {
  if (uploadResult) {
    const metadataRows = buildMetadataRows(uploadResult);

    return (
      <div className="border border-slate-200 rounded-sm bg-white overflow-hidden">
        <div
          className={cn(
            'px-4 py-3 border-b border-slate-200 flex items-center justify-between',
            isSuccess ? 'bg-[#3b963e]/10' : 'bg-[#b91c1c]/10',
          )}
        >
          <span className="text-[10px] font-bold uppercase tracking-wide text-slate-500">
            Intake Process Result
          </span>
          <span
            className={cn(
              'inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-sm text-white',
              isSuccess ? 'bg-[#3b963e]' : 'bg-[#b91c1c]',
            )}
          >
            {isSuccess ? 'Processed' : 'Failed'}
          </span>
        </div>

        <div className="p-4 space-y-4">
          <div className="flex items-start gap-3">
            {isSuccess ? (
              <CheckCircle className="size-5 text-[#3b963e] shrink-0 mt-0.5" aria-hidden="true" />
            ) : (
              <XCircle className="size-5 text-[#b91c1c] shrink-0 mt-0.5" aria-hidden="true" />
            )}
            <div className="min-w-0 flex-1">
              <p className="text-sm font-bold text-slate-900 truncate">{uploadResult.title}</p>
              <p className="text-xs text-slate-500 font-semibold mt-1 uppercase tracking-wide">
                {sourceTypeLabels[uploadResult.sourceType]}
                {uploadResult.evaluationReadiness && uploadResult.evaluationReadiness !== 'PENDING'
                  ? ` • ${uploadResult.evaluationReadiness}`
                  : null}
              </p>
            </div>
          </div>

          {isSuccess ? (
            <div className="border-t border-slate-100 pt-3 space-y-2">
              {metadataRows.length > 0 ? (
                metadataRows.map((row) => (
                  <MetadataRow key={row.label} label={row.label} value={row.value} />
                ))
              ) : (
                <p className="text-xs font-medium text-slate-500">
                  No additional metadata detected.
                </p>
              )}
            </div>
          ) : null}

          {isFailed && uploadResult.errorMessage && (
            <div className="border border-[#b91c1c]/30 bg-[#b91c1c]/10 rounded-sm p-3 text-xs font-semibold text-[#b91c1c]">
              {uploadResult.errorMessage}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="border border-slate-200 rounded-sm overflow-hidden bg-white">
      <div className="bg-slate-50 border-b border-slate-200 px-4 py-2.5">
        <span className="text-[10px] font-medium uppercase tracking-wide text-slate-500">
          Intake Summary Ledger
        </span>
      </div>

      <div className="divide-y divide-slate-100 text-xs">
        {/* Type */}
        <div className="grid grid-cols-3 px-4 py-2.5">
          <span className="col-span-1 text-slate-500 font-medium uppercase tracking-wide text-[10px]">
            Type
          </span>
          <span className="col-span-2 text-slate-900 font-medium">
            {sourceTypeLabels[sourceType]}
          </span>
        </div>

        {/* File Attachment */}
        <div className="grid grid-cols-3 px-4 py-2.5">
          <span className="col-span-1 text-slate-500 font-medium uppercase tracking-wide text-[10px]">
            File
          </span>
          <span
            className={cn(
              'col-span-2 font-medium truncate',
              file ? 'text-[#3b963e]' : 'text-[#f2c811]',
            )}
          >
            {file ? file.name : 'PENDING ATTACHMENT'}
          </span>
        </div>
      </div>
    </div>
  );
}

function buildMetadataRows(result: DocumentUploadResponse): Array<{ label: string; value: string }> {
  const rows: Array<{ label: string; value: string }> = [];

  if (result.program) {
    rows.push({ label: 'Program', value: result.program });
  }

  if (result.courseCode) {
    rows.push({ label: 'Course Code', value: result.courseCode });
  } else if (result.courseTitle) {
    rows.push({ label: 'Course', value: result.courseTitle });
  }

  if (result.academicYear) {
    rows.push({ label: 'Sem/AY', value: result.academicYear });
  }

  if (result.lessonTitle) {
    rows.push({ label: 'Lesson Title', value: result.lessonTitle });
  }

  return rows;
}

function MetadataRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      <span className="col-span-1 text-[10px] font-medium uppercase tracking-wide text-slate-500">
        {label}
      </span>
      <span className="col-span-2 text-xs font-semibold text-slate-900">{value}</span>
    </div>
  );
}
