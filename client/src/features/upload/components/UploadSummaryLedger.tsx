import { CheckCircle, Spinner, XCircle } from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
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
      <div className="border border-border rounded-sm bg-surface overflow-hidden">
        <div
          className={cn(
            'px-4 py-3 border-b border-border flex items-center justify-between',
            isSuccess && 'bg-success-soft/30',
            isProcessing && 'bg-warning-soft/30',
            isFailed && 'bg-destructive-soft/30',
            !isSuccess && !isProcessing && !isFailed && 'bg-surface-subtle',
          )}
        >
          <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
            Intake Process Result
          </span>
          <Badge
            variant={
              isSuccess
                ? 'success'
                : isProcessing
                  ? 'warning'
                  : isFailed
                    ? 'destructive'
                    : 'neutral'
            }
          >
            {isSuccess
              ? 'Processed'
              : isProcessing
                ? 'Processing'
                : isFailed
                  ? 'Failed'
                  : uploadResult.processingStatus}
          </Badge>
        </div>

        <div className="p-4 space-y-4">
          <div className="flex items-start gap-3">
            {isSuccess ? (
              <CheckCircle className="size-5 text-success shrink-0 mt-0.5" aria-hidden="true" />
            ) : isProcessing ? (
              <Spinner className="size-5 text-warning shrink-0 mt-0.5 animate-spin" aria-hidden="true" />
            ) : isFailed ? (
              <XCircle className="size-5 text-destructive shrink-0 mt-0.5" aria-hidden="true" />
            ) : null}
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-text truncate">{uploadResult.title}</p>
              <p className="text-xs text-text-muted font-medium mt-1 uppercase tracking-wide">
                {sourceTypeLabels[uploadResult.sourceType] ?? uploadResult.sourceType}
                {uploadResult.evaluationReadiness && uploadResult.evaluationReadiness !== 'PENDING'
                  ? ` • ${uploadResult.evaluationReadiness}`
                  : null}
              </p>
            </div>
          </div>

          {isProcessing ? (
            <div className="border border-border bg-surface-subtle rounded-sm p-3 text-xs text-text font-medium">
              Document intake is in progress. You do not need to upload again; you can track progress from My SLMs.
            </div>
          ) : null}

          {isSuccess || isProcessing ? (
            <div className="border-t border-border pt-3 space-y-2">
              {metadataRows.length > 0 ? (
                metadataRows.map((row) => (
                  <MetadataRow key={row.label} label={row.label} value={row.value} />
                ))
              ) : isSuccess ? (
                <p className="text-xs font-medium text-text-muted">
                  No additional metadata detected.
                </p>
              ) : null}
            </div>
          ) : null}

          {isFailed && (
            <div className="border border-destructive/30 bg-destructive-soft rounded-sm p-3 text-xs font-semibold text-destructive">
              {uploadResult.errorMessage || 'Document processing failed during upload intake. Please check the file and try again.'}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="border border-border rounded-sm overflow-hidden bg-surface">
      <div className="bg-surface-subtle border-b border-border px-4 py-2.5">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
          Intake Summary Ledger
        </span>
      </div>

      <div className="divide-y divide-border text-xs">
        {/* Type */}
        <div className="grid grid-cols-3 px-4 py-2.5">
          <span className="col-span-1 text-text-muted font-medium uppercase tracking-wider text-[10px]">
            Type
          </span>
          <span className="col-span-2 text-text font-medium">
            {sourceTypeLabels[sourceType] ?? sourceType}
          </span>
        </div>

        {/* File Attachment */}
        <div className="grid grid-cols-3 px-4 py-2.5">
          <span className="col-span-1 text-text-muted font-medium uppercase tracking-wider text-[10px]">
            File
          </span>
          <span
            className={cn(
              'col-span-2 font-medium truncate',
              file ? 'text-success font-semibold' : 'text-warning font-semibold',
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
      <span className="col-span-1 text-[10px] font-medium uppercase tracking-wider text-text-muted">
        {label}
      </span>
      <span className="col-span-2 text-xs font-semibold text-text">{value}</span>
    </div>
  );
}
