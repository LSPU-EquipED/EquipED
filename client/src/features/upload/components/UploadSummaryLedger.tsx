import { CheckCircle, Loader2, XCircle } from 'lucide-react';
import { cn } from '@/shared/components/utils';
import type { DocumentUploadResponse } from '@/shared/types/documents';
import {
  isFailedStatus,
  isProcessingStatus,
  isTerminalSuccessStatus,
} from '../utils/uploadFlow';

interface UploadSummaryLedgerProps {
  uploadResult: DocumentUploadResponse | null;
  isSuccess?: boolean;
  isProcessing?: boolean;
  isFailed?: boolean;
  file: File | null;
  sourceTypeLabels: Record<string, string>;
  sourceType: string;
}

export function UploadSummaryLedger({
  uploadResult,
  isSuccess: isSuccessProp,
  isProcessing: isProcessingProp,
  isFailed: isFailedProp,
  file,
  sourceTypeLabels,
  sourceType,
}: UploadSummaryLedgerProps) {
  const isSuccess = isSuccessProp ?? isTerminalSuccessStatus(uploadResult?.processingStatus);
  const isProcessing = isProcessingProp ?? isProcessingStatus(uploadResult?.processingStatus);
  const isFailed = isFailedProp ?? isFailedStatus(uploadResult?.processingStatus);

  if (uploadResult) {
    const metadataRows = buildMetadataRows(uploadResult);

    return (
      <div className="border border-slate-200 rounded-sm bg-white overflow-hidden">
        <div
          className={cn(
            'px-4 py-3 border-b border-slate-200 flex items-center justify-between',
            isSuccess && 'bg-[#3b963e]/10',
            isProcessing && 'bg-[#f2c811]/15',
            isFailed && 'bg-[#b91c1c]/10',
            !isSuccess && !isProcessing && !isFailed && 'bg-slate-50',
          )}
        >
          <span className="text-[10px] font-bold uppercase tracking-wide text-slate-500">
            Intake Process Result
          </span>
          <span
            className={cn(
              'inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-sm',
              isSuccess && 'bg-[#3b963e] text-white',
              isProcessing && 'bg-[#f2c811] text-[#1e293b]',
              isFailed && 'bg-[#b91c1c] text-white',
              !isSuccess && !isProcessing && !isFailed && 'bg-slate-200 text-slate-700',
            )}
          >
            {isSuccess
              ? 'Processed'
              : isProcessing
                ? 'Processing'
                : isFailed
                  ? 'Failed'
                  : uploadResult.processingStatus}
          </span>
        </div>

        <div className="p-4 space-y-4">
          <div className="flex items-start gap-3">
            {isSuccess ? (
              <CheckCircle className="size-5 text-[#3b963e] shrink-0 mt-0.5" aria-hidden="true" />
            ) : isProcessing ? (
              <Loader2 className="size-5 text-[#854d0e] shrink-0 mt-0.5 animate-spin" aria-hidden="true" />
            ) : isFailed ? (
              <XCircle className="size-5 text-[#b91c1c] shrink-0 mt-0.5" aria-hidden="true" />
            ) : null}
            <div className="min-w-0 flex-1">
              <p className="text-sm font-bold text-slate-900 truncate">{uploadResult.title}</p>
              <p className="text-xs text-slate-500 font-semibold mt-1 uppercase tracking-wide">
                {sourceTypeLabels[uploadResult.sourceType] ?? uploadResult.sourceType}
                {uploadResult.evaluationReadiness && uploadResult.evaluationReadiness !== 'PENDING'
                  ? ` • ${uploadResult.evaluationReadiness}`
                  : null}
              </p>
            </div>
          </div>

          {isProcessing ? (
            <div className="border border-slate-200 bg-slate-50/70 rounded-sm p-3 text-xs text-slate-700 font-medium">
              Document intake is in progress. You do not need to upload again; you can track progress from My SLMs.
            </div>
          ) : null}

          {isSuccess || isProcessing ? (
            <div className="border-t border-slate-100 pt-3 space-y-2">
              {metadataRows.length > 0 ? (
                metadataRows.map((row) => (
                  <MetadataRow key={row.label} label={row.label} value={row.value} />
                ))
              ) : isSuccess ? (
                <p className="text-xs font-medium text-slate-500">
                  No additional metadata detected.
                </p>
              ) : null}
            </div>
          ) : null}

          {isFailed && (
            <div className="border border-[#b91c1c]/30 bg-[#b91c1c]/10 rounded-sm p-3 text-xs font-semibold text-[#b91c1c]">
              {uploadResult.errorMessage || 'Document processing failed during upload intake. Please check the file and try again.'}
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
            {sourceTypeLabels[sourceType] ?? sourceType}
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

function buildMetadataRows(
  result: DocumentUploadResponse,
): Array<{ label: string; value: string }> {
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
