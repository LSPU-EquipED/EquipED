import { useRef, useState, type ChangeEvent, type FormEvent, type DragEvent } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { ArrowRight, GraduationCap, Loader2 } from 'lucide-react';
import { useAuth } from '@/features/auth/hooks/useAuth';
import { useUploadDocument } from '@/features/upload/hooks/useUploadDocument';
import type { DocumentSourceType, DocumentUploadResponse } from '@/shared/types/documents';

import { UploadHeader } from './UploadHeader';
import { UploadIntakeFields } from './UploadIntakeFields';
import { UploadDropzone } from './UploadDropzone';
import { UploadSummaryLedger } from './UploadSummaryLedger';

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
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(false);

    const droppedFile = event.dataTransfer.files?.[0] ?? null;
    if (droppedFile) {
      if (
        droppedFile.type === 'application/pdf' ||
        droppedFile.name.toLowerCase().endsWith('.pdf')
      ) {
        setFile(droppedFile);
        setUploadResult(null);
        resetUpload(null);

        if (!title.trim()) {
          setTitle(droppedFile.name.replace(/\.pdf$/i, ''));
        }
      }
    }
  };

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
      className="grid min-h-[calc(100vh-4rem)] w-full grid-cols-1 xl:grid-cols-[minmax(0,1fr)_30rem]"
    >
      <section className="flex min-h-[34rem] min-w-0 flex-col border-b xl:border-b-0 xl:border-r border-slate-200 bg-white">
        <UploadHeader title={title} />

        <div className="flex-1 px-4 py-6 sm:px-6 lg:px-8 max-w-4xl space-y-6">
          <div className="space-y-1 border-l-2 border-[#f2c811] pl-3">
            <h3 className="text-lg font-semibold tracking-tight text-slate-900">
              LSPU SCC Faculty Document Intake
            </h3>
            <p className="text-[10px] leading-relaxed text-slate-500 font-semibold uppercase tracking-wide">
              Laguna State Polytechnic University • Quality Assurance System
            </p>
          </div>

          <UploadIntakeFields
            title={title}
            setTitle={setTitle}
            program={program}
            handleProgramChange={handleProgramChange}
            subject={subject}
            setSubject={setSubject}
            programLabels={programLabels}
            subjectsByProgram={subjectsByProgram}
          />

          <UploadDropzone
            file={file}
            isDragging={isDragging}
            handleDragOver={handleDragOver}
            handleDragLeave={handleDragLeave}
            handleDrop={handleDrop}
            handleFileChange={handleFileChange}
            handleReset={handleReset}
            fileInputRef={fileInputRef}
          />
        </div>

        <div className="flex min-h-14 flex-wrap items-center gap-3 border-t border-slate-200 px-4 py-3 text-xs text-slate-500 font-semibold uppercase tracking-wide sm:px-6 bg-slate-50/20">
          <span className="inline-flex items-center gap-2">
            <GraduationCap className="size-4" aria-hidden="true" />
            Reference links stay out of scope in this phase.
          </span>
        </div>
      </section>

      <aside className="flex min-h-[34rem] flex-col bg-slate-50/30">
        <div className="border-b border-slate-200 px-4 py-7 sm:px-7 sm:py-8 bg-slate-50/50">
          <h3 className="text-lg font-semibold tracking-tight text-slate-900">
            Welcome back, {user?.displayName?.split(' ')?.[0] ?? 'there'}.
          </h3>
          <p className="mt-1 text-[10px] text-slate-500 font-medium uppercase tracking-wide leading-relaxed">
            {isSuccess
              ? 'Your document has been uploaded and processed successfully.'
              : isFailed
                ? 'Upload completed, but document processing failed.'
                : 'Review the upload details, then add the document to the dashboard inventory.'}
          </p>
        </div>

        <div className="grid gap-4 px-4 py-6 sm:px-7">
          <UploadSummaryLedger
            uploadResult={uploadResult}
            isSuccess={isSuccess}
            isFailed={isFailed}
            file={file}
            program={program}
            subject={subject}
            programLabels={programLabels}
            sourceTypeLabels={sourceTypeLabels}
            sourceType={sourceType}
          />

          {errorMessage ? (
            <div className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 px-4 py-3 text-sm text-[#b91c1c] font-semibold">
              {errorMessage}
            </div>
          ) : null}
        </div>

        <div className="border-t border-slate-200 bg-white px-4 py-3 sm:px-7">
          <div className="space-y-3">
            {uploadResult ? (
              <>
                <div className="flex items-center justify-between text-xs font-semibold text-slate-500">
                  <span>Status</span>
                  <span className="text-slate-800 font-bold">
                    {isSuccess ? 'Complete' : 'Failed'}
                  </span>
                </div>
                {isSuccess ? (
                  <button
                    type="button"
                    className="h-10 w-full inline-flex items-center justify-between bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-white px-4 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87] focus:outline-none"
                    onClick={() =>
                      navigate({
                        to: '/dashboard',
                        search: { highlight: uploadResult.documentId },
                      })
                    }
                  >
                    Go to Dashboard
                    <ArrowRight className="size-4" aria-hidden="true" />
                  </button>
                ) : (
                  <button
                    type="button"
                    className="h-10 w-full inline-flex items-center justify-between border border-slate-200 hover:bg-slate-50 text-slate-700 px-4 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87] focus:outline-none"
                    onClick={handleReset}
                  >
                    Try Uploading Again
                    <ArrowRight className="size-4" aria-hidden="true" />
                  </button>
                )}
                <p className="text-center text-xs font-medium text-slate-500 leading-relaxed">
                  {isSuccess
                    ? 'The document is now in your dashboard inventory.'
                    : 'You can try uploading the file again or contact support if the issue persists.'}
                </p>
              </>
            ) : (
              <>
                <div className="flex items-center justify-between text-xs font-semibold text-slate-500">
                  <span>Upload readiness</span>
                  <span className="text-slate-800 font-bold">
                    {file && title.trim() ? 'Ready' : 'Missing details'}
                  </span>
                </div>
                <button
                  type="submit"
                  className="h-10 w-full inline-flex items-center justify-between bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-white px-4 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87] focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
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
                      <ArrowRight className="size-4" aria-hidden="true" />
                    </span>
                  )}
                </button>
                <p className="text-center text-xs font-medium text-slate-500 leading-relaxed">
                  Uploading adds the document to inventory only. Evaluation is a later workflow.
                </p>
              </>
            )}
          </div>
        </div>
      </aside>
    </form>
  );
}
