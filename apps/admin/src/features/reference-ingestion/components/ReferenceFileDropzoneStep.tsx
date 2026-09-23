import type { ChangeEvent, DragEvent, Ref } from 'react';
import { UploadSimple } from '@phosphor-icons/react';
import { Button } from '@equiped/ui';
import { cn } from '@equiped/ui';

interface ReferenceFileDropzoneStepProps {
  title: string;
  onTitleChange: (title: string) => void;
  file: File | null;
  fileInputRef: Ref<HTMLInputElement>;
  isDragging: boolean;
  onDragOver: (event: DragEvent<HTMLLabelElement>) => void;
  onDragLeave: () => void;
  onDrop: (event: DragEvent<HTMLLabelElement>) => void;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  fileValidationError: string | null;
  isLoading: boolean;
  canSubmit: boolean;
  onReset: () => void;
  showReset: boolean;
}

export function ReferenceFileDropzoneStep({
  title,
  onTitleChange,
  file,
  fileInputRef,
  isDragging,
  onDragOver,
  onDragLeave,
  onDrop,
  onFileChange,
  fileValidationError,
  isLoading,
  canSubmit,
  onReset,
  showReset,
}: ReferenceFileDropzoneStepProps) {
  return (
    <div className="space-y-5 p-5 sm:p-6">
      <div className="space-y-1">
        <h2 className="text-base font-semibold text-text">Document details</h2>
        <p className="text-sm text-text-muted">Give the source a clear title and attach the official PDF.</p>
      </div>
      <div className="space-y-2">
        <label
          htmlFor="ref-title"
          className="block text-xs font-semibold text-text"
        >
          Title <span className="text-destructive">*</span>
        </label>
        <input
          type="text"
          id="ref-title"
          value={title}
          onChange={(e) => onTitleChange(e.target.value)}
          placeholder="e.g. IT101 Computer Programming 1 Syllabus 2026"
          className="w-full h-10 px-3 border border-input bg-surface rounded-sm text-sm font-normal text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring placeholder:text-text-muted"
          required
        />
      </div>
      <div className="space-y-2">
        <label
          htmlFor="ref-file"
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          className={cn(
            'flex min-h-40 cursor-pointer flex-col items-center justify-center gap-3 rounded-sm border border-dashed border-border bg-surface-subtle/50 px-5 py-7',
            'transition-colors hover:border-border-strong hover:bg-surface-subtle focus-within:ring-2 focus-within:ring-ring',
            isDragging && 'border-primary bg-primary-soft/60',
            file && !isDragging && 'border-primary/40 bg-primary-soft/20',
          )}
        >
          <UploadSimple className="size-6 text-text-muted" aria-hidden="true" />
          <span className="max-w-full break-words text-sm font-medium leading-relaxed text-text text-center">
            {file ? file.name : 'Drop a PDF here or browse files'}
          </span>
          <span className="text-center text-xs leading-relaxed text-text-muted">
            {file ? 'Click or drop a PDF to replace it' : 'PDF format only'}
          </span>
          <input
            id="ref-file"
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            onChange={onFileChange}
            className="sr-only"
          />
        </label>
        {fileValidationError ? (
          <p role="alert" className="text-xs font-semibold text-destructive mt-1">
            {fileValidationError}
          </p>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
        <Button
          variant="primary"
          size="md"
          disabled={isLoading || !canSubmit}
          isLoading={isLoading}
          className="font-semibold text-xs sm:text-sm h-10 px-5"
        >
          <span>Ingest document</span>
        </Button>

        {showReset ? (
          <Button
            type="button"
            variant="secondary"
            size="md"
            onClick={onReset}
            className="text-xs sm:text-sm h-10 px-4"
          >
            Reset form
          </Button>
        ) : null}
      </div>
    </div>
  );
}
