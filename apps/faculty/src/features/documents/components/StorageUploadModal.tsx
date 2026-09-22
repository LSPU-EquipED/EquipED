import { useEffect } from 'react';
import {
  CloudArrowUp,
  FileText,
  Spinner,
  Trash,
  WarningCircle,
} from '@phosphor-icons/react';
import { CANONICAL_PROGRAMS } from '@equiped/types';
import { Button, Dropdown, cn, usePresence } from '@equiped/ui';
import { useStorageUpload } from '../hooks/useStorageUpload';
import { formatFileSize } from '../utils/storage.utils';

interface StorageUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function StorageUploadModal({ isOpen, onClose, onSuccess }: StorageUploadModalProps) {
  const { isMounted, isAnimating } = usePresence({ isOpen, durationMs: 180 });

  const {
    file,
    title,
    setTitle,
    program,
    setProgram,
    isDragging,
    setIsDragging,
    isUploading,
    error,
    fileInputRef,
    handleFileChange,
    handleDrop,
    handleSubmit,
  } = useStorageUpload({ isOpen, onSuccess });

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isUploading) onClose();
    };
    if (isMounted) {
      window.addEventListener('keydown', handleKey);
      return () => window.removeEventListener('keydown', handleKey);
    }
  }, [isMounted, isUploading, onClose]);

  if (!isMounted) return null;

  return (
    <div
      className={cn(
        'fixed inset-0 z-50 flex items-center justify-center bg-foreground/45 p-4 transition-opacity duration-180 ease-out overflow-hidden backdrop-blur-2xs',
        isAnimating ? 'opacity-100' : 'opacity-0',
      )}
      onClick={() => {
        if (!isUploading) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="slm-upload-dialog-title"
        className={cn(
          'w-full max-w-lg rounded-md border border-border bg-surface p-6 sm:p-7 shadow-xl overflow-hidden',
          isAnimating ? 'animate-ledger-modal-in' : 'animate-ledger-modal-out',
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header without divider or eyebrow badge */}
        <div className="flex items-start justify-between">
          <div>
            <h2 id="slm-upload-dialog-title" className="text-base font-semibold text-text sm:text-lg">
              Upload Course Learning Module
            </h2>
            <p className="text-xs text-text-muted mt-1">
              Add a Self-Paced Learning Module (PDF) to the repository for parsing and evaluation.
            </p>
          </div>
        </div>

        {/* Modal Form */}
        <form onSubmit={handleSubmit} className="mt-5 space-y-4.5">
          {error && (
            <div
              role="alert"
              className="rounded-sm border border-destructive/30 bg-destructive-soft px-3.5 py-2.5 text-xs font-medium text-destructive flex items-start gap-2.5"
            >
              <WarningCircle className="size-4 shrink-0 mt-0.5" aria-hidden="true" />
              <div className="flex-1 min-w-0">
                <span className="font-semibold block">Upload Failed</span>
                <span>{error}</span>
              </div>
            </div>
          )}

          {/* Drag & Drop Zone or Selected File Card */}
          <div>
            <input
              ref={fileInputRef}
              id="slm-upload-file-input"
              type="file"
              accept=".pdf,application/pdf"
              onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
              className="sr-only"
            />

            {!file ? (
              <label
                htmlFor="slm-upload-file-input"
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                className={cn(
                  'group flex flex-col items-center justify-center p-6 border-2 border-dashed rounded-md cursor-pointer transition-all duration-150 text-center select-none',
                  isDragging
                    ? 'border-primary bg-primary-soft/40 shadow-xs'
                    : 'border-border hover:border-primary/50 bg-surface-subtle/40 hover:bg-surface-subtle',
                )}
              >
                <div className="mb-2.5 flex size-10 items-center justify-center rounded-sm border border-primary/15 bg-primary-soft text-primary transition-transform group-hover:scale-105 group-hover:bg-primary-soft/80">
                  <CloudArrowUp className="size-5" aria-hidden="true" />
                </div>
                <p className="text-xs font-semibold text-text">
                  Drag & drop your SLM PDF here, or{' '}
                  <span className="text-primary underline underline-offset-2 decoration-primary/40 group-hover:decoration-primary">
                    browse files
                  </span>
                </p>
                <p className="text-[11px] text-text-muted mt-1 font-mono">
                  PDF format only (up to 50 MB)
                </p>
              </label>
            ) : (
              <div className="rounded-md border border-border bg-surface p-3 sm:p-3.5 flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="size-9 rounded-sm bg-destructive-soft text-destructive border border-destructive/20 flex flex-col items-center justify-center shrink-0 font-mono text-[9px] font-bold uppercase tracking-wider">
                    <FileText className="size-3.5 mb-0.5" aria-hidden="true" />
                    <span>PDF</span>
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-bold text-text truncate" title={file.name}>
                      {file.name}
                    </p>
                    <p className="text-[11px] text-text-muted font-mono tabular-nums mt-0.5">
                      {formatFileSize(file.size)}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isUploading}
                    className="px-2.5 py-1 text-xs font-medium text-text-muted hover:text-text hover:bg-surface-subtle border border-border rounded-sm transition-colors cursor-pointer disabled:opacity-40"
                    title="Replace selected PDF"
                  >
                    Replace
                  </button>
                  <button
                    type="button"
                    onClick={() => handleFileChange(null)}
                    disabled={isUploading}
                    className="p-1 text-text-muted hover:text-destructive hover:bg-destructive-soft rounded-sm transition-colors cursor-pointer disabled:opacity-40"
                    title="Remove file"
                    aria-label="Remove selected file"
                  >
                    <Trash className="size-4" aria-hidden="true" />
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Module Title */}
          <div className="space-y-1.5">
            <label htmlFor="modal-slm-title" className="block text-xs font-semibold text-text">
              Module Title <span className="text-destructive">*</span>
            </label>
            <input
              id="modal-slm-title"
              type="text"
              required
              disabled={isUploading}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Data Structures & Algorithms Module"
              className="h-10 w-full rounded-sm border border-input bg-surface px-3 text-xs sm:text-sm font-medium text-text placeholder:text-text-muted/60 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-transparent disabled:cursor-not-allowed disabled:opacity-50"
            />
            <p className="text-[11px] text-text-muted">
              Auto-filled from file name. Adjust to match the syllabus title if needed.
            </p>
          </div>

          {/* Academic Program Dropdown */}
          <div className="space-y-1.5">
            <Dropdown
              id="modal-slm-program"
              label="Academic Program"
              required
              disabled={isUploading}
              size="md"
              value={program}
              onChange={(val) => setProgram(val as string)}
              options={CANONICAL_PROGRAMS.map((prog) => ({
                value: prog,
                label:
                  prog === 'BSCS'
                    ? 'BSCS — Bachelor of Science in Computer Science'
                    : 'BSInfoTech — Bachelor of Science in Information Technology',
              }))}
              className="w-full"
            />
          </div>

          {/* Footer Action Bar (No divider line) */}
          <div className="flex items-center justify-end gap-2.5 pt-2">
            <Button
              type="button"
              variant="secondary"
              size="md"
              onClick={onClose}
              disabled={isUploading}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="md"
              disabled={!file || !title.trim() || isUploading}
              className="gap-2 font-medium text-xs"
            >
              {isUploading ? (
                <>
                  <Spinner className="size-3.5 animate-spin" aria-hidden="true" />
                  <span>Indexing Module…</span>
                </>
              ) : (
                <>
                  <CloudArrowUp className="size-4" aria-hidden="true" />
                  <span>Upload & Index</span>
                </>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
