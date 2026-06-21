import type { ChangeEvent, DragEvent, RefObject } from 'react';
import { FileText, Upload } from 'lucide-react';
import { cn } from '@/shared/components/utils';

interface UploadDropzoneProps {
  file: File | null;
  isDragging: boolean;
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
  handleDragOver,
  handleDragLeave,
  handleDrop,
  handleFileChange,
  handleReset,
  fileInputRef,
}: UploadDropzoneProps) {
  return (
    <div className="space-y-2.5">
      <div className="text-[10px] font-bold uppercase tracking-wide text-slate-500">
        Document Attachment
      </div>

      <label
        htmlFor="pdf-file"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          'relative flex flex-col md:flex-row items-center justify-between gap-4 rounded-sm border border-dashed border-slate-300 bg-slate-50/50 p-4 transition-all cursor-pointer',
          'hover:border-slate-400 hover:bg-slate-50/80',
          'focus-within:ring-2 focus-within:ring-[#1b3b87] focus-within:ring-offset-2 focus-within:outline-none',
          isDragging && 'border-[#1b3b87] bg-blue-50/50 ring-2 ring-[#1b3b87]/20',
          file && 'border-solid border-[#1b3b87]/20 bg-white'
        )}
      >
        {/* Left Column: Icon and Info */}
        <div className="flex items-center gap-3 min-w-0 w-full md:w-auto">
          <div className={cn(
            "flex size-10 items-center justify-center rounded-sm border transition-colors shrink-0",
            file 
              ? "bg-[#1b3b87]/5 border-[#1b3b87]/20 text-[#1b3b87]" 
              : "bg-slate-100 border-slate-200 text-slate-400"
          )}>
            {file ? (
              <FileText className="size-5" aria-hidden="true" />
            ) : (
              <Upload className="size-5" aria-hidden="true" />
            )}
          </div>
          <div className="min-w-0">
            <p className={cn(
              "text-sm font-medium truncate",
              file ? "text-slate-800" : "text-slate-500"
            )}>
              {file ? file.name : "Select or drag the SLM PDF file"}
            </p>
            <p className="text-[10px] text-slate-500 font-medium uppercase tracking-wide mt-0.5">
              {file 
                ? `${(file.size / 1024 / 1024).toFixed(2)} MB • PDF Document` 
                : "PDF ONLY • SYSTEM INTAKE"}
            </p>
          </div>
        </div>

        {/* Right Column: Browse/Remove Actions */}
        <div className="flex items-center gap-2 shrink-0 w-full md:w-auto justify-end">
          {file ? (
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handleReset();
              }}
              className="h-8 px-3 border border-slate-200 hover:bg-slate-50 text-slate-600 rounded-sm text-xs font-bold uppercase tracking-wide transition-colors focus:ring-2 focus:ring-slate-200"
            >
              Remove File
            </button>
          ) : (
            <span className="h-8 px-4 inline-flex items-center justify-center bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-white rounded-sm text-xs font-bold uppercase tracking-wide transition-colors">
              Browse Files
            </span>
          )}
        </div>

        <input
          id="pdf-file"
          ref={fileInputRef}
          type="file"
          accept="application/pdf"
          onChange={handleFileChange}
          className="sr-only"
        />
      </label>
    </div>
  );
}
