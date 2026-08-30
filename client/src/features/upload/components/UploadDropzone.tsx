import type { ChangeEvent, DragEvent, RefObject } from 'react';
import { FileText, UploadSimple } from '@phosphor-icons/react';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/components/utils';

interface UploadDropzoneProps {
  file: File | null;
  isDragging: boolean;
  validationError?: string | null;
  handleDragOver: (e: DragEvent<HTMLLabelElement>) => void;
  handleDragLeave: () => void;
  handleDrop: (e: DragEvent<HTMLLabelElement>) => void;
  handleFileChange: (e: ChangeEvent<HTMLInputElement>) => void;
  handleReset: () => void;
  fileInputRef: RefObject<HTMLInputElement>;
}

export function UploadDropzone({
  file,
  isDragging,
  validationError,
  handleDragOver,
  handleDragLeave,
  handleDrop,
  handleFileChange,
  handleReset,
  fileInputRef,
}: UploadDropzoneProps) {
  return (
    <div className="space-y-2.5">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
        Document Attachment
      </div>

      <label
        htmlFor="pdf-file"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          'relative flex flex-col md:flex-row items-center justify-between gap-4 rounded-sm border border-dashed border-border bg-surface-subtle/50 p-4 transition-all cursor-pointer',
          'hover:border-primary/50 hover:bg-surface-subtle',
          'focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 focus-within:outline-none',
          isDragging && 'border-primary bg-primary-soft/30 ring-2 ring-primary/20',
          validationError && !file && 'border-destructive/50 bg-destructive-soft/30',
          file && 'border-solid border-border bg-surface',
        )}
      >
        {/* Left Column: Icon and Info */}
        <div className="flex items-center gap-3 min-w-0 w-full md:w-auto">
          <div
            className={cn(
              'flex size-10 items-center justify-center rounded-sm border transition-colors shrink-0',
              file
                ? 'bg-primary-soft border-primary/20 text-primary'
                : validationError
                  ? 'bg-destructive-soft border-destructive/30 text-destructive'
                  : 'bg-primary-soft/40 border-border text-primary',
            )}
          >
            {file ? (
              <FileText className="size-5" aria-hidden="true" />
            ) : (
              <UploadSimple className="size-5" aria-hidden="true" />
            )}
          </div>
          <div className="min-w-0">
            <p
              className={cn(
                'text-sm font-medium truncate',
                file ? 'text-text font-semibold' : 'text-text-muted',
              )}
            >
              {file ? file.name : 'Select or drag the SLM PDF file'}
            </p>
            <p className="text-[10px] text-text-muted font-medium uppercase tracking-wide mt-0.5">
              {file
                ? `${(file.size / 1024 / 1024).toFixed(2)} MB • PDF Document`
                : 'PDF ONLY • SYSTEM INTAKE'}
            </p>
          </div>
        </div>

        {/* Right Column: Browse/Remove Actions */}
        <div className="flex items-center gap-2 shrink-0 w-full md:w-auto justify-end">
          {file ? (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handleReset();
              }}
              className="uppercase tracking-wider font-semibold text-xs"
            >
              Remove File
            </Button>
          ) : (
            <span className="h-8 px-4 inline-flex items-center justify-center bg-primary hover:bg-primary-strong text-primary-foreground rounded-sm text-xs font-semibold uppercase tracking-wider transition-colors">
              Browse Files
            </span>
          )}
        </div>

        <input
          id="pdf-file"
          ref={fileInputRef}
          type="file"
          accept="application/pdf,.pdf"
          onChange={handleFileChange}
          aria-invalid={Boolean(validationError)}
          aria-describedby={validationError ? 'pdf-file-error' : undefined}
          className="sr-only"
        />
      </label>

      {validationError ? (
        <div
          id="pdf-file-error"
          role="alert"
          aria-live="polite"
          className="rounded-sm border border-destructive/30 bg-destructive-soft px-3 py-2 text-xs font-semibold text-destructive"
        >
          {validationError}
        </div>
      ) : null}
    </div>
  );
}
