import { useRef, useState, type ChangeEvent, type FormEvent } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { ArrowRight, CheckCircle, FileText, GraduationCap, Loader2, Upload, XCircle } from 'lucide-react';
import { useAuth } from '@/features/auth/hooks/useAuth';
import { useUploadDocument } from '@/features/upload/hooks/useUploadDocument';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
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
  bsit: ['Capstone Project 1', 'Web Systems and Technologies', 'Systems Integration and Architecture'],
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
  const [sourceType, setSourceType] = useState<DocumentSourceType>('slm');
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
        courseTitle: subject,
        program: sourceType === 'slm' ? program : null,
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

  const requiresProgram = sourceType === 'slm';

  const isSuccess = uploadResult?.processingStatus === 'PROCESSED';
  const isFailed = uploadResult?.processingStatus === 'FAILED';

  return (
    <form
      onSubmit={handleSubmit}
      className="mx-auto grid min-h-[calc(100vh-7.75rem)] w-full max-w-[108rem] grid-cols-1 overflow-hidden rounded-lg bg-card ring-1 ring-border xl:grid-cols-[minmax(0,1fr)_30rem]"
    >
      <section className="flex min-h-[34rem] min-w-0 flex-col border-b xl:border-b-0 xl:border-r">
        <div className="flex min-h-16 flex-wrap items-center justify-between gap-3 border-b px-4 py-3 sm:px-6">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Document workspace</p>
            <h2 className="truncate text-lg font-semibold">{title.trim() || 'Untitled document upload'}</h2>
          </div>
          <div className="rounded-full bg-muted px-3 py-1 text-xs font-medium text-muted-foreground">Upload only • evaluation later</div>
        </div>

        <div className="grid flex-1 place-items-center px-4 py-8 sm:px-6 lg:px-8">
          <div className="w-full max-w-3xl space-y-6 text-center">
            <div className="mx-auto flex size-16 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <FileText className="size-8" aria-hidden="true" />
            </div>

            <div className="space-y-2">
              <h3 className="text-2xl font-semibold">Upload an SLM or reference document</h3>
              <p className="mx-auto max-w-xl text-sm leading-6 text-muted-foreground">
                Add the document to the authenticated inventory. Processing status will appear in the dashboard after upload.
              </p>
            </div>

            <Label
              htmlFor="pdf-file"
              className={cn(
                'flex min-h-40 cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-muted/40 px-4 py-8 sm:px-6',
                'transition-colors hover:border-foreground/30 hover:bg-muted'
              )}
            >
              <Upload className="size-7 text-foreground" aria-hidden="true" />
              <span className="max-w-full truncate text-base font-medium">{file ? file.name : 'Drop a PDF here or browse files'}</span>
              <span className="text-center text-sm text-muted-foreground">PDF only. Upload size limit remains TBD in the TDD.</span>
              <Input id="pdf-file" ref={fileInputRef} type="file" accept="application/pdf" onChange={handleFileChange} className="sr-only" />
            </Label>

            <div className="grid gap-4 text-left md:grid-cols-2">
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="document-title">Title</Label>
                <Input
                  id="document-title"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="Enter the document title"
                  className="h-10 rounded-lg"
                  required
                />
              </div>

              <div className="space-y-2">
                <Label>Source type</Label>
                <Select value={sourceType} onValueChange={(value) => setSourceType(value as DocumentSourceType)}>
                  <SelectTrigger className="h-10 rounded-lg">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(Object.keys(sourceTypeLabels) as DocumentSourceType[]).map((sourceTypeKey) => (
                      <SelectItem key={sourceTypeKey} value={sourceTypeKey}>
                        {sourceTypeLabels[sourceTypeKey]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Program</Label>
                <Select value={program} onValueChange={handleProgramChange} disabled={!requiresProgram}>
                  <SelectTrigger className="h-10 rounded-lg">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(Object.keys(programLabels) as ProgramId[]).map((programId) => (
                      <SelectItem key={programId} value={programId}>
                        {programLabels[programId]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">{requiresProgram ? 'Program is required for SLM uploads.' : 'Program is optional for this source type.'}</p>
              </div>

              <div className="space-y-2 md:col-span-2">
                <Label>Course title</Label>
                <Select value={subject} onValueChange={setSubject}>
                  <SelectTrigger className="h-10 rounded-lg">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {subjectsByProgram[program].map((subjectName) => (
                      <SelectItem key={subjectName} value={subjectName}>
                        {subjectName}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        </div>

        <div className="flex min-h-14 flex-wrap items-center justify-between gap-3 border-t px-4 py-3 text-sm text-muted-foreground sm:px-6">
          <div className="flex min-w-0 flex-wrap items-center gap-3">
            <span className="inline-flex items-center gap-2">
              <GraduationCap className="size-4" aria-hidden="true" />
              Reference links stay out of scope in this phase.
            </span>
          </div>
          <span>Evaluations and reports will be wired in a later change.</span>
        </div>
      </section>

      <aside className="flex min-h-[34rem] flex-col bg-muted/20">
        <div className="border-b px-4 py-7 sm:px-7 sm:py-8">
          <h3 className="text-2xl font-semibold">Welcome back, {user?.displayName?.split(' ')?.[0] ?? 'there'}.</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            {isSuccess
              ? 'Your document has been uploaded and processed successfully.'
              : isFailed
                ? 'Upload completed, but document processing failed.'
                : 'Review the upload details, then add the document to the dashboard inventory.'}
          </p>
        </div>

        <div className="grid gap-4 px-4 py-6 sm:px-7">
          {uploadResult ? (
            <div className="rounded-lg border bg-card px-5 py-4">
              <div className="flex items-start gap-3">
                {isSuccess ? (
                  <CheckCircle className="mt-0.5 size-5 shrink-0 text-emerald-600" aria-hidden="true" />
                ) : (
                  <XCircle className="mt-0.5 size-5 shrink-0 text-rose-600" aria-hidden="true" />
                )}
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-muted-foreground">Result</p>
                  <p className="mt-1 text-base font-semibold">{uploadResult.title}</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {sourceTypeLabels[uploadResult.sourceType]}
                    {uploadResult.evaluationReadiness && uploadResult.evaluationReadiness !== 'PENDING'
                      ? ` • ${uploadResult.evaluationReadiness}`
                      : null}
                  </p>
                  <div className="mt-3">
                    <span
                      className={cn(
                        'inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium',
                        isSuccess
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-rose-100 text-rose-800'
                      )}
                    >
                      {isSuccess ? 'Ready' : 'Processing failed'}
                    </span>
                  </div>
                  {isFailed && uploadResult.errorMessage ? (
                    <p className="mt-2 text-sm text-destructive">{uploadResult.errorMessage}</p>
                  ) : null}
                </div>
              </div>
            </div>
          ) : (
            <>
              <div className="rounded-lg border bg-card px-5 py-4">
                <p className="text-sm font-medium text-muted-foreground">Source type</p>
                <p className="mt-1 text-base font-semibold">{sourceTypeLabels[sourceType]}</p>
              </div>

              <div className="rounded-lg border bg-card px-5 py-4">
                <p className="text-sm font-medium text-muted-foreground">Current file</p>
                <p className="mt-1 truncate text-base font-semibold">{file?.name ?? 'No PDF selected yet'}</p>
              </div>

              <div className="rounded-lg border bg-card px-5 py-4">
                <p className="text-sm font-medium text-muted-foreground">Program and course</p>
                <p className="mt-1 text-base font-semibold">{requiresProgram ? programLabels[program] : 'Optional program context'}</p>
                <p className="text-sm text-muted-foreground">{subject}</p>
              </div>
            </>
          )}

          {errorMessage ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{errorMessage}</div>
          ) : null}
        </div>

        <div className="sticky bottom-0 mt-auto border-t bg-card/95 px-4 py-4 shadow-[0_-10px_30px_rgba(0,0,0,0.04)] backdrop-blur sm:px-7">
          <div className="space-y-4">
            {uploadResult ? (
              <>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Status</span>
                  <span className="font-medium">{isSuccess ? 'Complete' : 'Failed'}</span>
                </div>
                {isSuccess ? (
                  <Button
                    type="button"
                    className="h-14 w-full justify-between rounded-lg px-5 text-base"
                    onClick={() =>
                      navigate({
                        to: '/dashboard',
                        search: { highlight: uploadResult.documentId },
                      })
                    }
                  >
                    Go to dashboard
                    <ArrowRight className="size-5" aria-hidden="true" />
                  </Button>
                ) : (
                  <Button
                    type="button"
                    variant="outline"
                    className="h-14 w-full justify-between rounded-lg px-5 text-base"
                    onClick={handleReset}
                  >
                    Try uploading again
                    <ArrowRight className="size-5" aria-hidden="true" />
                  </Button>
                )}
                <p className="text-center text-sm text-muted-foreground">
                  {isSuccess
                    ? 'The document is now in your dashboard inventory.'
                    : 'You can try uploading the file again or contact support if the issue persists.'}
                </p>
              </>
            ) : (
              <>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Upload readiness</span>
                  <span className="font-medium">{file && title.trim() ? 'Ready' : 'Missing details'}</span>
                </div>
                <Button type="submit" className="h-14 w-full justify-between rounded-lg px-5 text-base" disabled={isLoading || !file || !title.trim()}>
                  {isLoading ? (
                    <span className="inline-flex items-center gap-2">
                      <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                      Uploading and processing…
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-2">
                      Upload document
                      <ArrowRight className="size-5" aria-hidden="true" />
                    </span>
                  )}
                </Button>
                <p className="text-center text-sm text-muted-foreground">
                  Uploading adds the document to inventory only. Evaluation remains a later workflow.
                </p>
              </>
            )}
          </div>
        </div>
      </aside>
    </form>
  );
}
