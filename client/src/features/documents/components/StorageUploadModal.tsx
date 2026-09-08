import { useState, useRef, type DragEvent, type FormEvent, useEffect } from 'react';
import { CloudArrowUp, FileText, Spinner, WarningCircle, X } from '@phosphor-icons/react';
import { documentsApi } from '@/shared/api/documents.api';
import { CANONICAL_PROGRAMS } from '@/shared/constants/programs';
import { Button } from '@/shared/components/Button';
import { getErrorMessage } from '@/shared/api/http';

interface StorageUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function StorageUploadModal({ isOpen, onClose, onSuccess }: StorageUploadModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [program, setProgram] = useState('BSCS');
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKey);
      return () => window.removeEventListener('keydown', handleKey);
    }
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleFileChange = (selected: File | null) => {
    setError(null);
    if (!selected) {
      setFile(null);
      return;
    }
    if (!selected.name.toLowerCase().endsWith('.pdf') && selected.type !== 'application/pdf') {
      setError('Only PDF files are supported for course SLMs.');
      setFile(null);
      return;
    }
    setFile(selected);
    if (!title.trim()) {
      setTitle(selected.name.replace(/\.pdf$/i, ''));
    }
  };

  const handleDrop = (e: DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) handleFileChange(dropped);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!file || !title.trim() || !program) return;
    setIsUploading(true);
    setError(null);

    try {
      await documentsApi.uploadDocument({
        file,
        sourceType: 'slm',
        title: title.trim(),
        program,
      });
      setIsUploading(false);
      onSuccess();
    } catch (err) {
      setIsUploading(false);
      setError(getErrorMessage(err, 'Failed to upload SLM document.'));
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/40 backdrop-blur-xs p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Upload Course SLM to Storage"
        className="w-full max-w-lg rounded-md border border-border bg-surface shadow-xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border bg-surface-subtle px-6 py-4">
          <div>
            <h2 className="text-base font-bold text-text">Upload to SLM Storage</h2>
            <p className="text-xs text-text-muted mt-0.5">
              Add a Self-Paced Learning Module PDF to the institutional repository.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close upload dialog"
            className="rounded-xs p-1 text-text-muted hover:text-text hover:bg-surface cursor-pointer"
          >
            <X className="size-4.5" aria-hidden="true" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {error && (
            <div className="rounded-sm border border-destructive/30 bg-destructive-soft p-3 text-xs text-destructive flex items-center gap-2">
              <WarningCircle className="size-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Drag and drop zone */}
          <div>
            <label
              htmlFor="slm-upload-file-input"
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              className={`flex flex-col items-center justify-center p-6 border-2 border-dashed rounded-md transition-colors cursor-pointer text-center ${
                isDragging
                  ? 'border-primary bg-primary-soft/30'
                  : 'border-border hover:border-primary/50 bg-surface-subtle/50'
              }`}
            >
              <input
                ref={fileInputRef}
                id="slm-upload-file-input"
                type="file"
                accept=".pdf,application/pdf"
                onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
                className="sr-only"
              />
              <CloudArrowUp className="size-8 text-primary mb-2" aria-hidden="true" />
              {file ? (
                <div className="space-y-0.5">
                  <span className="text-xs font-bold text-text block">{file.name}</span>
                  <span className="text-[11px] text-text-muted font-mono">
                    {(file.size / 1024).toFixed(1)} KB · PDF Document
                  </span>
                </div>
              ) : (
                <div className="space-y-0.5">
                  <span className="text-xs font-bold text-text block">
                    Click to browse or drag & drop SLM PDF
                  </span>
                  <span className="text-[11px] text-text-muted block">
                    Standard PDF course module (up to 50 MB)
                  </span>
                </div>
              )}
            </label>
          </div>

          {/* Module Title */}
          <div className="space-y-1.5">
            <label htmlFor="modal-slm-title" className="text-xs font-bold uppercase tracking-wider text-text block">
              Module Title <span className="text-destructive">*</span>
            </label>
            <input
              id="modal-slm-title"
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Data Structures & Algorithms Module"
              className="h-9 w-full rounded-sm border border-input bg-surface px-3 text-xs text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>

          {/* Academic Program */}
          <div className="space-y-1.5">
            <label htmlFor="modal-slm-program" className="text-xs font-bold uppercase tracking-wider text-text block">
              Academic Program <span className="text-destructive">*</span>
            </label>
            <select
              id="modal-slm-program"
              value={program}
              onChange={(e) => setProgram(e.target.value)}
              className="h-9 w-full rounded-sm border border-input bg-surface px-3 text-xs font-semibold text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer"
            >
              {CANONICAL_PROGRAMS.map((prog) => (
                <option key={prog} value={prog}>
                  {prog === 'BSCS' ? 'BSCS — Computer Science' : 'BSInfoTech — Information Technology'}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center justify-end gap-3 pt-2 border-t border-border">
            <Button type="button" variant="secondary" size="md" onClick={onClose} disabled={isUploading}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="md"
              disabled={!file || !title.trim() || isUploading}
              className="gap-2 font-bold uppercase tracking-wider text-xs"
            >
              {isUploading ? (
                <>
                  <Spinner className="size-3.5 animate-spin" aria-hidden="true" />
                  <span>Indexing…</span>
                </>
              ) : (
                <span>Upload & Index</span>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
