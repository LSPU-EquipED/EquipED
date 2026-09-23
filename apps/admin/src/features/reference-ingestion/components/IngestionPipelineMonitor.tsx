import { Link } from '@tanstack/react-router';
import { CheckCircle, Spinner, XCircle } from '@phosphor-icons/react';
import { Button } from '@equiped/ui';
import { cn } from '@equiped/ui';
import { BUTTON_STYLES } from '@equiped/ui';
import type { DocumentUploadResponse } from '@equiped/types';
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
              <h3 className="text-sm font-semibold text-destructive">
                Upload failed
              </h3>
              <p className="break-words text-sm text-destructive leading-relaxed">
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
            'rounded-md border p-5 space-y-4 transition-colors',
            isProcessing && 'border-primary/30 bg-primary-soft/40',
            isSuccess && 'border-success/30 bg-success-soft',
            isFailed && 'border-destructive/30 bg-destructive-soft',
          )}
        >
          <div className="flex items-start gap-3">
            {isProcessing ? (
              <Spinner className="size-5 text-primary motion-safe:animate-spin shrink-0 mt-0.5" aria-hidden="true" />
            ) : isSuccess ? (
              <CheckCircle className="size-5 text-success shrink-0 mt-0.5" aria-hidden="true" />
            ) : (
              <XCircle className="size-5 text-destructive shrink-0 mt-0.5" aria-hidden="true" />
            )}
            <div className="space-y-1 min-w-0 flex-1">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm font-semibold text-text">Ingestion status</span>
                <span
                  className={cn(
                    'inline-flex items-center rounded-sm px-2.5 py-0.5 text-xs font-medium',
                    isSuccess && 'bg-success-soft text-success border border-success/30',
                    isProcessing && 'bg-surface-subtle text-text-muted border border-border',
                    isFailed && 'bg-destructive text-white',
                  )}
                >
                  {isSuccess ? 'Ready' : isProcessing ? 'Processing…' : 'Failed'}
                </span>
              </div>
              <p className="mt-1 break-words text-sm font-medium leading-relaxed text-text">{uploadResult.title}</p>
              <p className="mt-0.5 text-xs text-text-muted">
                {sourceTypeLabels[uploadResult.sourceType as AdminUploadSourceType] ?? uploadResult.sourceType}
                {uploadResult.program ? ` · ${uploadResult.program}` : ''}
              </p>

              {isProcessing ? (
                <p className="mt-2 text-xs leading-relaxed text-text-muted">
                  Processing the reference in the background. You can leave this page and check the{' '}
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
                <p className="mt-2 break-words text-sm text-destructive leading-relaxed">
                  {uploadResult.errorMessage ||
                    'Document processing failed. Please verify the uploaded reference and try again.'}
                </p>
              ) : null}

              {isSuccess ? (
                <p className="mt-2 text-xs leading-relaxed text-success">
                  Reference is ready for evaluation grounding.
                </p>
              ) : null}
            </div>
          </div>

          {/* Action Buttons */}
          {isSuccess || isFailed ? <div className="pt-4 flex flex-wrap items-center gap-2 border-t border-border">
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
          </div> : null}
        </div>
      ) : null}
    </>
  );
}
