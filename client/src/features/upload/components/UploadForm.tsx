import { useState } from 'react';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { cn } from '@/shared/components/utils';

export function UploadForm() {
  const [sourceType, setSourceType] = useState<'slm' | 'syllabus' | 'curriculum'>('slm');
  const [file, setFile] = useState<File | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // TODO: Handle form submission
    console.log({ file, sourceType });
  };

  return (
    <div className="max-w-2xl space-y-6">
      <div className="space-y-2">
        <span className="text-xs uppercase tracking-wider text-primary/70">Upload</span>
        <h1 className="text-2xl font-semibold">Document submission</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Upload Documents</CardTitle>
          <CardDescription>Upload PDF files for evaluation</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="pdf-file">PDF file</Label>
              <Input
                id="pdf-file"
                type="file"
                accept="application/pdf"
                onChange={handleFileChange}
                className="cursor-pointer"
              />
              {file && <p className="text-sm text-muted-foreground">{file.name}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="source-type">Source type</Label>
              <select
                id="source-type"
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value as 'slm' | 'syllabus' | 'curriculum')}
                className={cn(
                  'flex h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-base transition-colors outline-none',
                  'focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50',
                  'disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-input/50 disabled:opacity-50',
                  'aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20',
                  'dark:bg-input/30 dark:disabled:bg-input/80 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40'
                )}
              >
                <option value="slm">SLM</option>
                <option value="syllabus">Syllabus</option>
                <option value="curriculum">Curriculum</option>
              </select>
            </div>

            <Button type="submit" className="w-fit">
              Upload Document
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
