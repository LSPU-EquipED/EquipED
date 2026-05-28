import { useRef, useState, type ChangeEvent, type FormEvent } from 'react';
import { CheckCircle, FileText, Loader2, Upload, XCircle } from 'lucide-react';
import { useAdminUpload } from '@/features/admin/hooks/useAdminUpload';
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
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Admin</p>
        <h1 className="mt-2 text-2xl font-semibold">Reference Ingestion</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Upload syllabi, rubrics, and curricula to the knowledge base for evaluation context.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="mx-auto grid w-full max-w-[48rem] gap-6 rounded-lg border bg-card p-6 shadow-sm"
      >
        <div className="space-y-2">
          <Label>Document Type</Label>
          <Select value={sourceType} onValueChange={(value) => setSourceType(value as ReferenceSourceType)}>
            <SelectTrigger className="h-10 rounded-lg">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {referenceTypes.map((type) => (
                <SelectItem key={type} value={type}>
                  {sourceTypeLabels[type]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="ref-title">Title</Label>
          <Input
            id="ref-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Enter the document title"
            className="h-10 rounded-lg"
            required
          />
        </div>

        <Label
          htmlFor="ref-file"
          className={cn(
            'flex min-h-40 cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-muted/40 px-4 py-8',
            'transition-colors hover:border-foreground/30 hover:bg-muted'
          )}
        >
          <Upload className="size-7 text-foreground" aria-hidden="true" />
          <span className="max-w-full truncate text-base font-medium">
            {file ? file.name : 'Drop a PDF here or browse files'}
          </span>
          <span className="text-center text-sm text-muted-foreground">PDF only. Reference documents for embedding.</span>
          <Input id="ref-file" ref={fileInputRef} type="file" accept="application/pdf" onChange={handleFileChange} className="sr-only" />
        </Label>

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
                <p className="mt-1 text-sm text-muted-foreground">{sourceTypeLabels[uploadResult.sourceType as ReferenceSourceType]}</p>
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
        ) : null}

        {errorMessage ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {errorMessage}
          </div>
        ) : null}

        <div className="flex items-center justify-end gap-3">
          {uploadResult ? (
            <Button type="button" variant="outline" onClick={handleReset}>
              Upload another
            </Button>
          ) : (
            <Button type="submit" disabled={isLoading || !file || !title.trim()}>
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
            </Button>
          )}
        </div>
      </form>
    </section>
  );
}
