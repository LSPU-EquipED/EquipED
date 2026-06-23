import { useRef, useState, type ChangeEvent, type FormEvent } from 'react';
import { CheckCircle, FileText, Loader2, Upload, XCircle } from 'lucide-react';
import { useAdminUpload } from '@/features/admin/hooks/useAdminUpload';
import { cn } from '@/shared/components/utils';
import type { DocumentSourceType, DocumentUploadResponse } from '@/shared/types/documents';

type ReferenceSourceType = Exclude<DocumentSourceType, 'slm'>;

const sourceTypeLabels: Record<ReferenceSourceType, string> = {
  syllabus: 'Syllabus',
  rubric_sme: 'SME Rubric',
  rubric_coord: 'Coordinator Rubric',
  rubric_gad: 'GAD Rubric',
  rubric_itso: 'ITSO Rubric',
  curriculum: 'Curriculum',
};

const referenceTypes: ReferenceSourceType[] = [
  'syllabus',
  'rubric_sme',
  'rubric_coord',
  'rubric_gad',
  'rubric_itso',
  'curriculum',
];

export function AdminUploadPage() {
  const { uploadDocument, isLoading, errorMessage, setData: resetUpload } = useAdminUpload();
  const [sourceType, setSourceType] = useState<ReferenceSourceType>('syllabus');
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
        sourceType,
        title,
      });
      setUploadResult(result);
    } catch {
      // Error state is surfaced via errorMessage from the hook
    }
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
    <section className="grid gap-6">

      <form
        onSubmit={handleSubmit}
        className="mx-auto grid w-full max-w-[48rem] gap-6 rounded-sm border border-slate-200 bg-white p-6"
      >
        <div className="space-y-2">
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500">Document Type</label>
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
          <label htmlFor="ref-title" className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Title
          </label>
          <input
            type="text"
            id="ref-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Enter the document title"
            className="w-full h-10 px-3 border border-slate-200 bg-white rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[#1b3b87] placeholder:text-slate-400 font-semibold text-slate-800"
            required
          />
        </div>

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
              PDF only. Reference documents for embedding.
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
                <CheckCircle
                  className="mt-0.5 size-5 shrink-0 text-emerald-600"
                  aria-hidden="true"
                />
              ) : (
                <XCircle className="mt-0.5 size-5 shrink-0 text-red-600" aria-hidden="true" />
              )}
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-455">Result</p>
                <p className="mt-1 text-base font-bold text-slate-900">{uploadResult.title}</p>
                <p className="mt-1 text-sm text-slate-500 font-semibold">
                  {sourceTypeLabels[uploadResult.sourceType as ReferenceSourceType]}
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
                  <p className="mt-2 text-sm font-semibold text-red-700">{uploadResult.errorMessage}</p>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}

        {errorMessage ? (
          <div className="rounded-sm border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 font-semibold">
            {errorMessage}
          </div>
        ) : null}

        <div className="flex items-center justify-end gap-3">
          {uploadResult ? (
            <button
              type="button"
              className="inline-flex h-10 items-center justify-center border border-slate-200 hover:bg-slate-50 text-slate-700 px-4 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-slate-200 focus:outline-none"
              onClick={handleReset}
            >
              Upload another
            </button>
          ) : (
            <button
              type="submit"
              className="inline-flex h-10 items-center justify-center bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-white px-4 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87] focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={isLoading || !file || !title.trim()}
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
