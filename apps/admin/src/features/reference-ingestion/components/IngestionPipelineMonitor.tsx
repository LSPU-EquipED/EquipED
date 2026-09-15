import { Link } from '@tanstack/react-router';
import { CheckCircle, Spinner, XCircle } from '@phosphor-icons/react';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/components/utils';
import { BUTTON_STYLES } from '@/shared/constants/theme';
import type { DocumentUploadResponse } from '@/shared/types/documents';
import type { AdminUploadSourceType } from '../types';
import { sourceTypeLabels } from './ReferenceClassificationStep';

interface IngestionPipelineMonitorProps {
  errorMessage: string | null;
  uploadResult: DocumentUploadResponse | null;
  onReset: () => void;
}

export function IngestionPipelineMonitor({
  errorMessage,
  uploadResult,
  onReset,
}: IngestionPipelineMonitorProps) {
  const isProcessing = uploadResult?.processingStatus === 'PROCESSING';
  const isSuccess = uploadResult?.processingStatus === 'PROCESSED';
  const isFailed = uploadResult?.processingStatus === 'FAILED';

  return (
    <>
      {/* Initial Upload Rejection Alert (when uploadDocument rejects before background task) */}
      {errorMessage && !uploadResult ? (
        <div
          role="alert"
          aria-live="assertive"
          className="rounded-md border border-destructive/30 bg-destructive-soft p-5 space-y-3.5"
        >
          <div className="flex items-start gap-3">
            <XCircle className="size-5 text-destructive shrink-0 mt-0.5" aria-hidden="true" />
            <div className="space-y-1 min-w-0">
              <h3 className="text-xs font-bold text-destructive tracking-tight">
                Upload Failed
              </h3>
              <p className="text-[11px] text-destructive/90 leading-relaxed">
                {errorMessage}
              </p>
            </div>
          </div>
          <div className="pt-2 border-t border-destructive/20">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={onReset}
              className="text-xs h-8 px-3"
            >
              Try again
            </Button>
          </div>
        </div>
      ) : null}

      {/* Pipeline Monitor Card (When Uploaded / Polling / Completed / Failed) */}
      {uploadResult ? (
        <div
          role={isFailed ? 'alert' : 'status'}
          aria-live={isFailed ? 'assertive' : 'polite'}
          className={cn(
            'rounded-md border p-4 space-y-3 transition-colors',
            isProcessing && 'border-primary/30 bg-primary-soft/40',
            isSuccess && 'border-success/30 bg-success-soft',
            isFailed && 'border-destructive/30 bg-destructive-soft',
          )}
        >
          <div className="flex items-start gap-3">
            {isProcessing ? (
              <Spinner className="size-5 text-primary animate-spin shrink-0 mt-0.5" aria-hidden="true" />
            ) : isSuccess ? (
              <CheckCircle className="size-5 text-success shrink-0 mt-0.5" aria-hidden="true" />
            ) : (
              <XCircle className="size-5 text-destructive shrink-0 mt-0.5" aria-hidden="true" />
            )}
            <div className="space-y-1 min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                  Result
                </span>
                <span
                  className={cn(
                    'inline-flex items-center rounded-sm px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider',
                    isSuccess && 'bg-success-soft text-success border border-success/30',
                    isProcessing && 'bg-surface-subtle text-text-muted border border-border',
                    isFailed && 'bg-destructive text-white',
                  )}
                >
                  {isSuccess ? 'Ready' : isProcessing ? 'Processing…' : 'Failed'}
                </span>
              </div>
              <p className="mt-1 text-sm font-bold text-text truncate">{uploadResult.title}</p>
              <p className="mt-0.5 text-xs text-text-muted font-semibold">
                {sourceTypeLabels[uploadResult.sourceType as AdminUploadSourceType] ?? uploadResult.sourceType}
                {uploadResult.program ? ` · ${uploadResult.program}` : ''}
              </p>

              {isProcessing ? (
                <p className="mt-2 text-xs font-semibold text-text-muted leading-relaxed">
                  Extracting and embedding the document in the background. This can take several
                  minutes for scanned PDFs — you can leave this page; check the{' '}
                  <Link
                    to="/admin/references"
                    className="underline text-primary"
                  >
                    reference library
                  </Link>{' '}
                  for status.
                </p>
              ) : null}

              {isFailed ? (
                <p className="mt-2 text-sm font-semibold text-destructive leading-relaxed">
                  {uploadResult.errorMessage ||
                    'Document processing failed. Please verify the uploaded reference and try again.'}
                </p>
              ) : null}

              {isSuccess ? (
                <p className="mt-2 text-xs font-semibold text-success leading-relaxed">
                  Document has been parsed, chunked, and embedded into local ChromaDB for evaluation retrieval.
                </p>
              ) : null}
            </div>
          </div>

          {/* Action Buttons */}
          <div className="pt-2 flex flex-wrap items-center gap-2 border-t border-border">
            {isSuccess ? (
              <Link
                to="/admin/references"
                className={cn(
                  BUTTON_STYLES.base,
                  BUTTON_STYLES.variants.primary,
                  BUTTON_STYLES.sizes.sm,
                  'text-xs h-8 px-3',
                )}
              >
                <span>View in reference library</span>
              </Link>
            ) : isFailed ? (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={onReset}
                className="text-xs h-8 px-3"
              >
                Try again
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}
    </>
  );
}
