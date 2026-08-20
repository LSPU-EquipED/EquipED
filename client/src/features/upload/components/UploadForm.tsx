import { useRef, useState, type ChangeEvent, type FormEvent, type DragEvent } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { useQueryClient } from '@tanstack/react-query';
import { ArrowRight, GraduationCap, Loader2 } from 'lucide-react';
import { useAuth } from '@/features/auth/hooks/useAuth';
import { useUploadDocument } from '@/features/upload/hooks/useUploadDocument';
import type { DocumentUploadResponse } from '@/shared/types/documents';
import {
  isFailedStatus,
  isPdfFile,
  isProcessingStatus,
  isTerminalSuccessStatus,
  shouldNavigateToEvaluation,
} from '@/features/upload/utils/uploadFlow';

import { UploadHeader } from './UploadHeader';
import { UploadIntakeFields } from './UploadIntakeFields';
import { UploadDropzone } from './UploadDropzone';
import { UploadSummaryLedger } from './UploadSummaryLedger';

const sourceType = 'slm';

const sourceTypeLabels: Record<string, string> = {
  slm: 'SLM',
};

function titleFromFilename(filename: string): string {
  return filename.replace(/\.pdf$/i, '');
}

export function UploadForm() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { uploadDocument, isLoading, errorMessage, setData: resetUpload } = useUploadDocument();
  const [title, setTitle] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<DocumentUploadResponse | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigationTriggeredRef = useRef(false);

  const handleDragOver = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const applyFile = (nextFile: File | null) => {
    setFile(nextFile);
    setUploadResult(null);
    resetUpload(null);

    if (!nextFile) {
      return;
    }

    if (!title.trim()) {
      setTitle(titleFromFilename(nextFile.name));
    }
  };

  const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(false);

    const droppedFile = event.dataTransfer.files?.[0] ?? null;
    if (!droppedFile) {
      return;
    }

    if (!isPdfFile(droppedFile)) {
      setValidationError('Only PDF documents are supported for SLM upload. Please select a valid .pdf file.');
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      return;
    }

    setValidationError(null);
    applyFile(droppedFile);
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0] ?? null;
    if (!selectedFile) {
      return;
    }

    if (!isPdfFile(selectedFile)) {
      setValidationError('Only PDF documents are supported for SLM upload. Please select a valid .pdf file.');
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      return;
    }

    setValidationError(null);
    applyFile(selectedFile);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!file || !title.trim() || !isPdfFile(file)) {
      return;
    }

    setUploadResult(null);
    setValidationError(null);

    try {
      const result = await uploadDocument({
        file,
        sourceType,
        title,
      });
      setUploadResult(result);

      // A processed SLM continues to its evaluation page exactly once.
      // Non-terminal processing and failed results stay on the upload experience.
      if (shouldNavigateToEvaluation(result) && !navigationTriggeredRef.current) {
        navigationTriggeredRef.current = true;
        void queryClient.invalidateQueries({ queryKey: ['documents'] });
        void navigate({
          to: '/documents/$documentId/evaluation',
          params: { documentId: result.documentId },
        });
      }
    } catch {
      // Error state is surfaced via errorMessage from the hook
    }
  };

  const handleReset = () => {
    setUploadResult(null);
    resetUpload(null);
    setFile(null);
    setTitle('');
    setValidationError(null);
    navigationTriggeredRef.current = false;
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const isSuccess = isTerminalSuccessStatus(uploadResult?.processingStatus);
  const isProcessing = isProcessingStatus(uploadResult?.processingStatus);
  const isFailed = isFailedStatus(uploadResult?.processingStatus);

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

          <UploadIntakeFields title={title} setTitle={setTitle} />

          <UploadDropzone
            file={file}
            isDragging={isDragging}
            validationError={validationError}
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
            Course and semester details are auto-detected from the document.
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
              : isProcessing
                ? 'Your document was uploaded and is currently processing in the background.'
                : isFailed
                  ? 'Upload completed, but document processing failed.'
                  : 'Review the upload details, then upload the document to begin.'}
          </p>
        </div>

        <div className="grid gap-4 px-4 py-6 sm:px-7">
          <UploadSummaryLedger
            uploadResult={uploadResult}
            isSuccess={isSuccess}
            isProcessing={isProcessing}
            isFailed={isFailed}
            file={file}
            sourceTypeLabels={sourceTypeLabels}
            sourceType={sourceType}
          />

          {errorMessage ? (
            <div
              role="alert"
              className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 px-4 py-3 text-sm text-[#b91c1c] font-semibold"
            >
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
                    {isSuccess ? 'Complete' : isProcessing ? 'Processing' : 'Failed'}
                  </span>
                </div>
                {isSuccess ? (
                  <button
                    type="button"
                    className="h-10 w-full inline-flex items-center justify-between bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-white px-4 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87] focus:outline-none"
                    onClick={() =>
                      navigate({
                        to: '/documents',
                        search: { highlight: uploadResult.documentId },
                      })
                    }
                  >
                    Go to My SLMs
                    <ArrowRight className="size-4" aria-hidden="true" />
                  </button>
                ) : isProcessing ? (
                  <button
                    type="button"
                    className="h-10 w-full inline-flex items-center justify-between bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-white px-4 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87] focus:outline-none"
                    onClick={() =>
                      navigate({
                        to: '/documents',
                        search: { highlight: uploadResult.documentId },
                      })
                    }
                  >
                    View in My SLMs
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
                    ? 'Continuing to the evaluation page…'
                    : isProcessing
                      ? 'Processing continues in the background. Check My SLMs to start evaluation once ready.'
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
                  After processing, you will continue to the evaluation page for this SLM.
                </p>
              </>
            )}
          </div>
        </div>
      </aside>
    </form>
  );
}
