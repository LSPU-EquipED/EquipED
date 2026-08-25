import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react';
import { Link } from '@tanstack/react-router';
import { ArrowLeft, CheckCircle, FileText, Loader2, Upload, XCircle } from 'lucide-react';
import { documentsApi } from '@/shared/api/documents.api';
import { ProgramSelector } from '@/shared/components/ProgramSelector';
import { cn } from '@/shared/components/utils';
import { LSPU_SCC_COLLEGE_PROGRAMS, normalizeProgram } from '@/shared/constants/programs';
import {
  POLICY_AREA_LABELS,
  POLICY_AREAS,
  type DocumentUploadResponse,
  type PolicyArea,
} from '@/shared/types/documents';
import { useAdminUpload } from '../hooks/useAdminUpload';
import type { AdminUploadSourceType } from '../types';

const POLL_INTERVAL_MS = 4000;

const sourceTypeLabels: Record<AdminUploadSourceType, string> = {
  syllabus: 'Syllabus',
  curriculum: 'Curriculum',
  policy: 'Policy',
};

const referenceTypes: AdminUploadSourceType[] = ['syllabus', 'curriculum', 'policy'];

export function AdminUploadPage() {
  const { uploadDocument, isLoading, errorMessage, setData: resetUpload } = useAdminUpload();
  const [sourceType, setSourceType] = useState<AdminUploadSourceType>('syllabus');
  const [title, setTitle] = useState('');
  const [program, setProgram] = useState('');
  const [policyArea, setPolicyArea] = useState<PolicyArea>('general_itso');
  const [file, setFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<DocumentUploadResponse | null>(null);
  const [programTouched, setProgramTouched] = useState(false);
  const [formAttempted, setFormAttempted] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isCurriculum = sourceType === 'curriculum';
  const isPolicyAreaRequired = sourceType === 'policy';
  const isProgramInvalid = isCurriculum && (programTouched || formAttempted) && !program.trim();

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const nextFile = event.target.files?.[0] ?? null;
    setFile(nextFile);
    setUploadResult(null);
    resetUpload(null);

    if (nextFile && !title.trim()) {
      setTitle(nextFile.name.replace(/\.pdf$/i, ''));
    }
  };

  const handleSourceTypeChange = (next: AdminUploadSourceType) => {
    setSourceType(next);
    setProgram('');
    setPolicyArea('general_itso');
    setUploadResult(null);
    setProgramTouched(false);
    setFormAttempted(false);
    resetUpload(null);
  };

  const handleProgramChange = (val: string) => {
    setProgramTouched(true);
    setProgram(normalizeProgram(val));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormAttempted(true);

    if (!file || !title.trim()) {
      return;
    }

    if (isCurriculum && !program.trim()) {
      return;
    }

    if (isPolicyAreaRequired && !policyArea) {
      return;
    }

    setUploadResult(null);

    try {
      const result = await uploadDocument({
        file,
        sourceType,
        title,
        program: isCurriculum ? program.trim() : undefined,
        policyArea: isPolicyAreaRequired ? policyArea : undefined,
      });
      setUploadResult({
        ...result,
        program: isCurriculum ? program.trim() : null,
      });
    } catch {
      // Error state is surfaced via errorMessage from the hook
    }
  };

  // Reference documents (syllabus/curriculum/policy) return PROCESSING immediately —
  // OCR/ingestion runs in a background task, so poll until it lands on PROCESSED/FAILED.
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
          const firstWarning = doc.processingWarnings?.find(
            (warning) => typeof warning === 'string' && warning.trim().length > 0,
          )?.trim();
          const fallbackError =
            'Document processing failed. Please verify the uploaded reference and try again.';
          const failedErrorMessage =
            doc.processingStatus === 'FAILED' ? firstWarning || fallbackError : undefined;

          setUploadResult((previous) =>
            previous
              ? {
                  ...previous,
                  processingStatus: doc.processingStatus,
                  academicYear: doc.academicYear,
                  courseCode: doc.courseCode,
                  program: doc.program ?? previous.program,
                  errorMessage: failedErrorMessage ?? previous.errorMessage,
                }
              : previous,
          );
        }
      } catch {
        // transient poll failure — try again on the next tick
      }
    };

    void poll();
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
    setPolicyArea('general_itso');
    setProgramTouched(false);
    setFormAttempted(false);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const isProcessing = uploadResult?.processingStatus === 'PROCESSING';
  const isSuccess = uploadResult?.processingStatus === 'PROCESSED';
  const isFailed = uploadResult?.processingStatus === 'FAILED';
  const canSubmit =
    !!file &&
    title.trim().length > 0 &&
    (!isCurriculum || !!program.trim()) &&
    (!isPolicyAreaRequired || !!policyArea);

  return (
    <section className="grid gap-6">
      <div className="mx-auto flex w-full max-w-[48rem] items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Admin</p>
          <h1 className="mt-1 text-xl font-bold text-slate-900">Reference Ingestion</h1>
        </div>
        <Link
          to="/admin/references"
          className="inline-flex h-10 min-h-[40px] items-center gap-2 border border-slate-200 bg-white px-3 text-sm font-semibold uppercase tracking-wide text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87] rounded-sm"
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          Back to library
        </Link>
      </div>

      <form
        onSubmit={handleSubmit}
        className="mx-auto grid w-full max-w-[48rem] gap-6 rounded-sm border border-slate-200 bg-white p-6"
      >
        <div className="space-y-2">
          <label
            htmlFor="ref-source-type"
            className="text-xs font-bold uppercase tracking-wider text-slate-500"
          >
            Document Type
          </label>
          <select
            id="ref-source-type"
            value={sourceType}
            onChange={(e) => handleSourceTypeChange(e.target.value as AdminUploadSourceType)}
            className="w-full h-10 min-h-[40px] border border-slate-200 bg-white px-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87] rounded-sm text-sm font-semibold text-slate-800"
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
            className="w-full h-10 min-h-[40px] px-3 border border-slate-200 bg-white rounded-sm text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87] placeholder:text-slate-500 font-semibold text-slate-800"
            required
          />
        </div>

        {isCurriculum ? (
          <div className="space-y-2">
            <ProgramSelector
              id="ref-program"
              label="Program"
              value={program}
              onChange={handleProgramChange}
              groups={LSPU_SCC_COLLEGE_PROGRAMS}
              placeholder="Select a program (BSCS or BSInfoTech)"
              required
              hint="Required for curriculum references. Associated with canonical BSCS or BSInfoTech."
            />
            {isProgramInvalid ? (
              <p
                id="ref-program-error"
                role="alert"
                className="text-xs font-semibold text-[#b91c1c] mt-1"
              >
                Please select a program for this curriculum document.
              </p>
            ) : null}
          </div>
        ) : null}

        {isPolicyAreaRequired ? (
          <div className="space-y-2">
            <label
              htmlFor="ref-policy-area"
              className="text-xs font-bold uppercase tracking-wider text-slate-500"
            >
              Policy Area
            </label>
            <select
              id="ref-policy-area"
              value={policyArea}
              onChange={(e) => setPolicyArea(e.target.value as PolicyArea)}
              className="w-full h-10 min-h-[40px] border border-slate-200 bg-white px-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87] rounded-sm text-sm font-semibold text-slate-800"
              required={isPolicyAreaRequired}
            >
              {POLICY_AREAS.map((area) => (
                <option key={area} value={area}>
                  {POLICY_AREA_LABELS[area]}
                </option>
              ))}
            </select>
            <p className="text-xs font-medium text-slate-500">
              Required for policy references. The area is used to route retrieval during ITSO
              evaluation.
            </p>
          </div>
        ) : null}

        <div className="space-y-2">
          <label
            htmlFor="ref-file"
            className={cn(
              'flex min-h-40 cursor-pointer flex-col items-center justify-center gap-3 rounded-sm border border-dashed border-slate-200 bg-slate-50/50 px-4 py-8',
              'transition-colors hover:border-slate-300 hover:bg-slate-50 focus-within:ring-2 focus-within:ring-[#1b3b87]',
            )}
          >
            <Upload className="size-7 text-slate-500" aria-hidden="true" />
            <span className="max-w-full truncate text-sm font-semibold text-slate-800">
              {file ? file.name : 'Drop a PDF here or browse files'}
            </span>
            <span className="text-center text-xs text-slate-500 font-medium">
              PDF only. Upload syllabus, curriculum, or policy references for embedding.
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
          <div
            role={isFailed ? 'alert' : 'status'}
            aria-live={isFailed ? 'assertive' : 'polite'}
            className="rounded-sm border border-slate-200 bg-white px-5 py-4"
          >
            <div className="flex items-start gap-3">
              {isSuccess ? (
                <CheckCircle className="mt-0.5 size-5 shrink-0 text-[#15803d]" aria-hidden="true" />
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
                <p className="mt-1 text-sm text-slate-600 font-semibold">
                  {sourceTypeLabels[uploadResult.sourceType as AdminUploadSourceType] ??
                    uploadResult.sourceType}
                  {uploadResult.program ? ` · ${uploadResult.program}` : ''}
                </p>
                <div className="mt-3">
                  <span
                    className={cn(
                      'inline-flex items-center rounded-sm px-2.5 py-1 text-xs font-semibold uppercase tracking-wider text-white',
                      isSuccess ? 'bg-[#15803d]' : isProcessing ? 'bg-slate-500' : 'bg-[#b91c1c]',
                    )}
                  >
                    {isSuccess ? 'Ready' : isProcessing ? 'Processing…' : 'Failed'}
                  </span>
                </div>
                {isProcessing ? (
                  <p className="mt-2 text-sm font-semibold text-slate-500">
                    Extracting and embedding the document in the background. This can take several
                    minutes for scanned PDFs — you can leave this page; check the{' '}
                    <Link
                      to="/admin/references"
                      className="underline focus-visible:ring-2 focus-visible:ring-[#1b3b87] rounded-sm"
                    >
                      reference library
                    </Link>{' '}
                    for status.
                  </p>
                ) : null}
                {isFailed ? (
                  <p className="mt-2 text-sm font-semibold text-[#b91c1c]">
                    {uploadResult.errorMessage ||
                      'Document processing failed. Please verify the uploaded reference and try again.'}
                  </p>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}

        {errorMessage ? (
          <div
            role="alert"
            aria-live="assertive"
            className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 px-4 py-3 text-sm text-[#b91c1c] font-semibold"
          >
            {errorMessage}
          </div>
        ) : null}

        <div className="flex items-center justify-end gap-3">
          {uploadResult ? (
            <button
              type="button"
              className="inline-flex h-10 min-h-[40px] items-center justify-center border border-slate-200 hover:bg-slate-50 text-slate-700 px-4 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus-visible:ring-2 focus-visible:ring-[#1b3b87] focus-visible:outline-none"
              onClick={handleReset}
            >
              Upload another
            </button>
          ) : (
            <button
              type="submit"
              className="inline-flex h-10 min-h-[40px] items-center justify-center bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-white px-4 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus-visible:ring-2 focus-visible:ring-[#1b3b87] focus-visible:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={isLoading || !canSubmit}
            >
              {isLoading ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  Ingesting...
                </span>
              ) : (
                <span className="inline-flex items-center gap-2">
                  <FileText className="size-4" aria-hidden="true" />
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
