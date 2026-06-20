import { useRef, useState, type ChangeEvent, type FormEvent } from 'react';
import { useNavigate } from '@tanstack/react-router';
import {
  ArrowRight,
  CheckCircle,
  FileText,
  GraduationCap,
  Loader2,
  Upload,
  XCircle,
} from 'lucide-react';
import { useAuth } from '@/features/auth/hooks/useAuth';
import { useUploadDocument } from '@/features/upload/hooks/useUploadDocument';
import { cn } from '@/shared/components/utils';
import type { DocumentSourceType, DocumentUploadResponse } from '@/shared/types/documents';

type ProgramId = 'bsit' | 'bscs' | 'bsis';

const sourceTypeLabels: Record<DocumentSourceType, string> = {
  slm: 'SLM',
  syllabus: 'Syllabus',
  rubric_sme: 'SME Rubric',
  rubric_coord: 'Coordinator Rubric',
  rubric_gad: 'GAD Rubric',
  rubric_itso: 'ITSO Rubric',
  curriculum: 'Curriculum',
};

const subjectsByProgram: Record<ProgramId, string[]> = {
  bsit: [
    'Capstone Project 1',
    'Web Systems and Technologies',
    'Systems Integration and Architecture',
  ],
  bscs: ['Software Engineering 2', 'Automata Theory', 'Intelligent Systems'],
  bsis: ['Business Process Management', 'Information Systems Planning', 'Enterprise Architecture'],
};

const programLabels: Record<ProgramId, string> = {
  bsit: 'BS Information Technology',
  bscs: 'BS Computer Science',
  bsis: 'BS Information Systems',
};

export function UploadForm() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { uploadDocument, isLoading, errorMessage, setData: resetUpload } = useUploadDocument();
  const [program, setProgram] = useState<ProgramId>('bsit');
  const [subject, setSubject] = useState(subjectsByProgram.bsit[0]);
  const sourceType: DocumentSourceType = 'slm';
  const [title, setTitle] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<DocumentUploadResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

    if (!file || !title.trim()) {
      return;
    }

    setUploadResult(null);

    try {
      const result = await uploadDocument({
        file,
        sourceType: 'slm',
        title,
        courseTitle: subject,
        program,
      });
      setUploadResult(result);
    } catch {
      // Error state is surfaced via errorMessage from the hook
    }
  };

  const handleProgramChange = (value: string) => {
    const nextProgram = value as ProgramId;
    setProgram(nextProgram);
    setSubject(subjectsByProgram[nextProgram][0]);
  };

  const handleReset = () => {
    setUploadResult(null);
    resetUpload(null);
    setFile(null);
    setTitle('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const isSuccess = uploadResult?.processingStatus === 'PROCESSED';
  const isFailed = uploadResult?.processingStatus === 'FAILED';

  return (
    <form
      onSubmit={handleSubmit}
      className="mx-auto grid min-h-[calc(100vh-7.75rem)] w-full max-w-[108rem] grid-cols-1 overflow-hidden rounded-sm border border-slate-200 bg-white xl:grid-cols-[minmax(0,1fr)_30rem]"
    >
      <section className="flex min-h-[34rem] min-w-0 flex-col border-b xl:border-b-0 xl:border-r border-slate-200">
        <div className="flex min-h-16 flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3 sm:px-6 bg-slate-50/50">
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">
              Document Workspace
            </p>
            <h2 className="truncate text-sm font-bold text-slate-900 mt-0.5">
              {title.trim() || 'Untitled document upload'}
            </h2>
          </div>
          <div className="rounded-sm bg-slate-100 border border-slate-200 px-3 py-1 text-xs font-bold uppercase tracking-wider text-slate-500">
            Upload only • evaluation later
          </div>
        </div>

        <div className="grid flex-1 place-items-center px-4 py-8 sm:px-6 lg:px-8">
          <div className="w-full max-w-3xl space-y-6 text-center">
            <div className="mx-auto flex size-16 items-center justify-center rounded-sm bg-slate-50 border border-slate-200 text-[#1b3b87]">
              <FileText className="size-8" aria-hidden="true" />
            </div>

            <div className="space-y-2">
              <h3 className="text-2xl font-bold text-slate-900">Upload an SLM</h3>
              <p className="mx-auto max-w-xl text-sm leading-6 text-slate-500 font-medium">
                Add your Self-Learning Module to the authenticated inventory. Processing status will
                appear in the dashboard after upload.
              </p>
            </div>

            <label
              htmlFor="pdf-file"
              className={cn(
                'flex min-h-40 cursor-pointer flex-col items-center justify-center gap-3 rounded-sm border border-dashed border-slate-200 bg-slate-50/50 px-4 py-8 sm:px-6',
                'transition-colors hover:border-slate-350 hover:bg-slate-50',
              )}
            >
              <Upload className="size-7 text-slate-500" aria-hidden="true" />
              <span className="max-w-full truncate text-base font-bold text-slate-800">
                {file ? file.name : 'Drop a PDF here or browse files'}
              </span>
              <span className="text-center text-xs text-slate-500 font-semibold">
                PDF only. Upload size limit remains TBD in the TDD.
              </span>
              <input
                id="pdf-file"
                ref={fileInputRef}
                type="file"
                accept="application/pdf"
                onChange={handleFileChange}
                className="sr-only"
              />
            </label>

            <div className="grid gap-4 text-left md:grid-cols-2">
              <div className="space-y-2 md:col-span-2">
                <label htmlFor="document-title" className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1.5 block">
                  Title
                </label>
                <input
                  id="document-title"
                  type="text"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="Enter the document title"
                  className="w-full h-10 px-3 border border-slate-200 bg-white rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[#1b3b87] placeholder:text-slate-400 font-semibold text-slate-800"
                  required
                />
              </div>

              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1.5 block">Program</label>
                <select
                  value={program}
                  onChange={(e) => handleProgramChange(e.target.value)}
                  className="w-full h-10 border border-slate-200 bg-white px-3 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] rounded-sm text-sm font-semibold text-slate-800 cursor-pointer"
                >
                  {(Object.keys(programLabels) as ProgramId[]).map((programId) => (
                    <option key={programId} value={programId}>
                      {programLabels[programId]}
                    </option>
                  ))}
                </select>
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                  Program is required for SLM uploads.
                </p>
              </div>

              <div className="space-y-2 md:col-span-2">
                <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1.5 block">Course Title</label>
                <select
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="w-full h-10 border border-slate-200 bg-white px-3 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] rounded-sm text-sm font-semibold text-slate-800 cursor-pointer"
                >
                  {subjectsByProgram[program].map((subjectName) => (
                    <option key={subjectName} value={subjectName}>
                      {subjectName}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </div>

        <div className="flex min-h-14 flex-wrap items-center justify-between gap-3 border-t border-slate-200 px-4 py-3 text-xs text-slate-500 font-semibold uppercase tracking-wider sm:px-6 bg-slate-50/20">
          <div className="flex min-w-0 flex-wrap items-center gap-3">
            <span className="inline-flex items-center gap-2">
              <GraduationCap className="size-4" aria-hidden="true" />
              Reference links stay out of scope in this phase.
            </span>
          </div>
          <span>Evaluations and reports will be wired in a later change.</span>
        </div>
      </section>

      <aside className="flex min-h-[34rem] flex-col bg-slate-50/30">
        <div className="border-b border-slate-200 px-4 py-7 sm:px-7 sm:py-8 bg-slate-50/50">
          <h3 className="text-xl font-bold text-slate-900">
            Welcome back, {user?.displayName?.split(' ')?.[0] ?? 'there'}.
          </h3>
          <p className="mt-1.5 text-xs text-slate-500 font-semibold uppercase tracking-wider leading-relaxed">
            {isSuccess
              ? 'Your document has been uploaded and processed successfully.'
              : isFailed
                ? 'Upload completed, but document processing failed.'
                : 'Review the upload details, then add the document to the dashboard inventory.'}
          </p>
        </div>

        <div className="grid gap-4 px-4 py-6 sm:px-7">
          {uploadResult ? (
            <div className="rounded-sm border border-slate-200 bg-white px-5 py-4">
              <div className="flex items-start gap-3">
                {isSuccess ? (
                  <CheckCircle
                    className="mt-0.5 size-5 shrink-0 text-emerald-605"
                    aria-hidden="true"
                  />
                ) : (
                  <XCircle className="mt-0.5 size-5 shrink-0 text-red-600" aria-hidden="true" />
                )}
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Result</p>
                  <p className="mt-1 text-base font-bold text-slate-900">{uploadResult.title}</p>
                  <p className="mt-1 text-xs text-slate-500 font-bold uppercase tracking-wider">
                    {sourceTypeLabels[uploadResult.sourceType]}
                    {uploadResult.evaluationReadiness &&
                    uploadResult.evaluationReadiness !== 'PENDING'
                      ? ` • ${uploadResult.evaluationReadiness}`
                      : null}
                  </p>
                  <div className="mt-3">
                    <span
                      className={cn(
                        'inline-flex items-center rounded-sm px-2.5 py-1 text-xs font-semibold uppercase tracking-wider text-white',
                        isSuccess ? 'bg-emerald-600' : 'bg-red-700',
                      )}
                    >
                      {isSuccess ? 'Ready' : 'Failed'}
                    </span>
                  </div>
                  {isFailed && uploadResult.errorMessage ? (
                    <p className="mt-2 text-sm font-semibold text-red-705">{uploadResult.errorMessage}</p>
                  ) : null}
                </div>
              </div>
            </div>
          ) : (
            <>
              <div className="rounded-sm border border-slate-200 bg-white px-5 py-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Source Type</p>
                <p className="mt-1 text-sm font-bold text-slate-900">{sourceTypeLabels[sourceType]}</p>
              </div>

              <div className="rounded-sm border border-slate-200 bg-white px-5 py-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Current File</p>
                <p className="mt-1 truncate text-sm font-bold text-slate-900">
                  {file?.name ?? 'No PDF selected yet'}
                </p>
              </div>

              <div className="rounded-sm border border-slate-200 bg-white px-5 py-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Program and Course</p>
                <p className="mt-1 text-sm font-bold text-slate-900">{programLabels[program]}</p>
                <p className="text-xs text-slate-500 font-bold uppercase tracking-wider mt-1">{subject}</p>
              </div>
            </>
          )}

          {errorMessage ? (
            <div className="rounded-sm border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 font-semibold">
              {errorMessage}
            </div>
          ) : null}
        </div>

        <div className="sticky bottom-0 mt-auto border-t border-slate-200 bg-white px-4 py-4 backdrop-blur sm:px-7">
          <div className="space-y-4">
            {uploadResult ? (
              <>
                <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-500">
                  <span>Status</span>
                  <span className="text-slate-800 font-bold">{isSuccess ? 'Complete' : 'Failed'}</span>
                </div>
                {isSuccess ? (
                  <button
                    type="button"
                    className="h-14 w-full inline-flex items-center justify-between bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-white px-5 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87]"
                    onClick={() =>
                      navigate({
                        to: '/dashboard',
                        search: { highlight: uploadResult.documentId },
                      })
                    }
                  >
                    Go to Dashboard
                    <ArrowRight className="size-5" aria-hidden="true" />
                  </button>
                ) : (
                  <button
                    type="button"
                    className="h-14 w-full inline-flex items-center justify-between border border-slate-200 hover:bg-slate-50 text-slate-700 px-5 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-slate-200"
                    onClick={handleReset}
                  >
                    Try Uploading Again
                    <ArrowRight className="size-5" aria-hidden="true" />
                  </button>
                )}
                <p className="text-center text-xs font-semibold text-slate-400 uppercase tracking-wider leading-relaxed">
                  {isSuccess
                    ? 'The document is now in your dashboard inventory.'
                    : 'You can try uploading the file again or contact support if the issue persists.'}
                </p>
              </>
            ) : (
              <>
                <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-500">
                  <span>Upload Readiness</span>
                  <span className="text-slate-800 font-bold">
                    {file && title.trim() ? 'Ready' : 'Missing details'}
                  </span>
                </div>
                <button
                  type="submit"
                  className="h-14 w-full inline-flex items-center justify-between bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-white px-5 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87] disabled:opacity-50 disabled:cursor-not-allowed"
                  disabled={isLoading || !file || !title.trim()}
                >
                  {isLoading ? (
                    <span className="inline-flex items-center gap-2">
                      <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                      Uploading and Processing…
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-2">
                      Upload Document
                      <ArrowRight className="size-5" aria-hidden="true" />
                    </span>
                  )}
                </button>
                <p className="text-center text-[10px] font-semibold text-slate-400 uppercase tracking-wider leading-relaxed">
                  Uploading adds the document to inventory only. Evaluation remains a later
                  workflow.
                </p>
              </>
            )}
          </div>
        </div>
      </aside>
    </form>
  );
}
