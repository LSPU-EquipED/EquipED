import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react';
import { Link } from '@tanstack/react-router';
import { ArrowLeft, CheckCircle, FileText, Loader2, Upload, XCircle } from 'lucide-react';
import { useAdminUpload } from '@/features/admin/hooks/useAdminUpload';
import { documentsApi } from '@/shared/api/documents.api';
import { cn } from '@/shared/components/utils';
import { ProgramSelector } from '@/shared/components/ProgramSelector';
import { LSPU_SCC_COLLEGE_PROGRAMS } from '@/shared/constants/programs';
import type { DocumentUploadResponse, ReferenceSourceType } from '@/shared/types/documents';

const POLL_INTERVAL_MS = 4000;

const sourceTypeLabels: Record<ReferenceSourceType, string> = {
  syllabus: 'Syllabus',
  curriculum: 'Curriculum',
};

const referenceTypes: ReferenceSourceType[] = ['syllabus', 'curriculum'];

export function AdminUploadPage() {
  const { uploadDocument, isLoading, errorMessage, setData: resetUpload } = useAdminUpload();
  const [sourceType, setSourceType] = useState<ReferenceSourceType>('syllabus');
  const [title, setTitle] = useState('');
  const [program, setProgram] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<DocumentUploadResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const isProgramRequired = sourceType === 'curriculum';

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const nextFile = event.target.files?.[0] ?? null;
    setFile(nextFile);
    setUploadResult(null);
    resetUpload(null);

    if (nextFile && !title.trim()) {
      setTitle(nextFile.name.replace(/\.pdf$/i, ''));
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!file || !title.trim() || (isProgramRequired && !program.trim())) {
      return;
    }

    setUploadResult(null);

    try {
      const result = await uploadDocument({
        file,
        sourceType,
        title,
        program: isProgramRequired ? program.trim().toUpperCase() : undefined,
      });
      setUploadResult(result);
    } catch {
      // Error state is surfaced via errorMessage from the hook
    }
  };

  // Reference documents (curriculum/syllabus) return PROCESSING immediately —
  // OCR runs in a background task, so poll until it lands on PROCESSED/FAILED.
  useEffect(() => {
    if (!uploadResult || uploadResult.processingStatus !== 'PROCESSING') {
      return;
    }

    let cancelled = false;
    const documentId = uploadResult.documentId;

    const poll = async () => {
      try {
        const doc = await documentsApi.getDocument(documentId);
        if (cancelled) return;
        if (doc.processingStatus !== 'PROCESSING') {
          setUploadResult((previous) =>
            previous
              ? {
                  ...previous,
                  processingStatus: doc.processingStatus,
                  academicYear: doc.academicYear,
                  courseCode: doc.courseCode,
                }
              : previous,
          );
        }
      } catch {
        // transient poll failure — try again on the next tick
      }
    };

    const intervalId = window.setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [uploadResult]);

  const handleReset = () => {
    setUploadResult(null);
    resetUpload(null);
    setFile(null);
    setTitle('');
    setProgram('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const isProcessing = uploadResult?.processingStatus === 'PROCESSING';
  const isSuccess = uploadResult?.processingStatus === 'PROCESSED';
  const isFailed = uploadResult?.processingStatus === 'FAILED';

  return (
    <section className="grid gap-6">
      <div className="mx-auto flex w-full max-w-[48rem] items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Admin
          </p>
          <h1 className="mt-1 text-xl font-bold text-slate-900">Reference Ingestion</h1>
        </div>
        <Link
          to="/admin/references"
          className="inline-flex h-10 items-center gap-2 border border-slate-200 bg-white px-3 text-sm font-semibold uppercase tracking-wide text-slate-700 transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] rounded-sm"
        >
          <ArrowLeft className="size-4" />
          Back to library
        </Link>
      </div>

      <form
        onSubmit={handleSubmit}
        className="mx-auto grid w-full max-w-[48rem] gap-6 rounded-sm border border-slate-200 bg-white p-6"
      >
        <div className="space-y-2">
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Document Type
          </label>
          <select
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value as ReferenceSourceType)}
            className="w-full h-10 border border-slate-200 bg-white px-3 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] rounded-sm text-sm font-semibold text-slate-800"
          >
            {referenceTypes.map((type) => (
              <option key={type} value={type}>
                {sourceTypeLabels[type]}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-2">
          <label
            htmlFor="ref-title"
            className="text-xs font-bold uppercase tracking-wider text-slate-500"
          >
            Title
          </label>
          <input
            type="text"
            id="ref-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Enter the document title"
            className="w-full h-10 px-3 border border-slate-200 bg-white rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[#1b3b87] placeholder:text-slate-600 font-semibold text-slate-800"
            required
          />
        </div>

        {isProgramRequired ? (
          <ProgramSelector
            id="ref-program"
            label="Program"
            value={program}
            onChange={setProgram}
            groups={LSPU_SCC_COLLEGE_PROGRAMS}
            placeholder="Select a program"
            required={isProgramRequired}
            hint="Required for curriculum references. Program codes are saved as uppercase."
          />
        ) : null}

        <div className="space-y-2">
          <label
            htmlFor="ref-file"
            className={cn(
              'flex min-h-40 cursor-pointer flex-col items-center justify-center gap-3 rounded-sm border border-dashed border-slate-200 bg-slate-50/50 px-4 py-8',
              'transition-colors hover:border-slate-300 hover:bg-slate-50',
            )}
          >
            <Upload className="size-7 text-slate-500" aria-hidden="true" />
            <span className="max-w-full truncate text-sm font-semibold text-slate-800">
              {file ? file.name : 'Drop a PDF here or browse files'}
            </span>
            <span className="text-center text-xs text-slate-500 font-medium">
              PDF only. Upload syllabus or curriculum references for embedding.
            </span>
            <input
              id="ref-file"
              ref={fileInputRef}
              type="file"
              accept="application/pdf"
              onChange={handleFileChange}
              className="sr-only"
            />
          </label>
        </div>

        {uploadResult ? (
          <div className="rounded-sm border border-slate-200 bg-white px-5 py-4">
            <div className="flex items-start gap-3">
              {isSuccess ? (
                <CheckCircle className="mt-0.5 size-5 shrink-0 text-[#3b963e]" aria-hidden="true" />
              ) : isProcessing ? (
                <Loader2
                  className="mt-0.5 size-5 shrink-0 animate-spin text-slate-500"
                  aria-hidden="true"
                />
              ) : (
                <XCircle className="mt-0.5 size-5 shrink-0 text-[#b91c1c]" aria-hidden="true" />
              )}
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Result
                </p>
                <p className="mt-1 text-base font-bold text-slate-900">{uploadResult.title}</p>
                <p className="mt-1 text-sm text-slate-500 font-semibold">
                  {sourceTypeLabels[uploadResult.sourceType as ReferenceSourceType]}
                </p>
                <div className="mt-3">
                  <span
                    className={cn(
                      'inline-flex items-center rounded-sm px-2.5 py-1 text-xs font-semibold uppercase tracking-wider text-white',
                      isSuccess ? 'bg-[#3b963e]' : isProcessing ? 'bg-slate-500' : 'bg-[#b91c1c]',
                    )}
                  >
                    {isSuccess ? 'Ready' : isProcessing ? 'Processing…' : 'Failed'}
                  </span>
                </div>
                {isProcessing ? (
                  <p className="mt-2 text-sm font-semibold text-slate-500">
                    Extracting and embedding the document in the background. This can take
                    several minutes for scanned PDFs — you can leave this page; check the{' '}
                    <Link to="/admin/references" className="underline">
                      reference library
                    </Link>{' '}
                    for status.
                  </p>
                ) : null}
                {isFailed && uploadResult.errorMessage ? (
                  <p className="mt-2 text-sm font-semibold text-[#b91c1c]">
                    {uploadResult.errorMessage}
                  </p>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}

        {errorMessage ? (
          <div className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 px-4 py-3 text-sm text-[#b91c1c] font-semibold">
            {errorMessage}
          </div>
        ) : null}

        <div className="flex items-center justify-end gap-3">
          {uploadResult ? (
            <button
              type="button"
              className="inline-flex h-10 items-center justify-center border border-slate-200 hover:bg-slate-50 text-slate-700 px-4 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87] focus:outline-none"
              onClick={handleReset}
            >
              Upload another
            </button>
          ) : (
            <button
              type="submit"
              className="inline-flex h-10 items-center justify-center bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-white px-4 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87] focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={isLoading || !file || !title.trim() || (isProgramRequired && !program.trim())}
            >
              {isLoading ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="size-4 animate-spin" />
                  Ingesting...
                </span>
              ) : (
                <span className="inline-flex items-center gap-2">
                  <FileText className="size-4" />
                  Ingest document
                </span>
              )}
            </button>
          )}
        </div>
      </form>
    </section>
  );
}
