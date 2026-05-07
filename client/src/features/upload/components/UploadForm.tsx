import { useState } from 'react';
import {
  ArrowRight,
  BookOpenCheck,
  Check,
  CheckSquare,
  FileSearch,
  FileText,
  GraduationCap,
  Link2,
  Sparkles,
  Upload,
} from 'lucide-react';
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

type ProgramId = 'bsit' | 'bscs' | 'bsis';

const scanOptions = [
  {
    id: 'sme',
    title: 'SME Review',
    description: 'Learning outcomes, content quality, assessment fit',
    icon: BookOpenCheck,
  },
  {
    id: 'coordinator',
    title: 'Coordinator Check',
    description: 'Program alignment and curriculum consistency',
    icon: GraduationCap,
  },
  {
    id: 'gad',
    title: 'GAD Review',
    description: 'Gender sensitivity and inclusive language',
    icon: Sparkles,
  },
  {
    id: 'itso',
    title: 'ITSO Review',
    description: 'Originality, citation, and technical compliance',
    icon: FileSearch,
  },
];

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
  const [program, setProgram] = useState<ProgramId>('bsit');
  const [subject, setSubject] = useState(subjectsByProgram.bsit[0]);
  const [file, setFile] = useState<File | null>(null);
  const [selectedChecks, setSelectedChecks] = useState(['sme', 'coordinator', 'gad', 'itso']);

  const toggleCheck = (id: string) => {
    setSelectedChecks((current) =>
      current.includes(id) ? current.filter((check) => check !== id) : [...current, id]
    );
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFile(e.target.files?.[0] ?? null);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log({ file, program, subject, selectedChecks });
  };

  const handleProgramChange = (value: string) => {
    const nextProgram = value as ProgramId;
    setProgram(nextProgram);
    setSubject(subjectsByProgram[nextProgram][0]);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="mx-auto grid min-h-[calc(100vh-7.75rem)] w-full max-w-[108rem] grid-cols-1 overflow-hidden rounded-lg bg-card ring-1 ring-border xl:grid-cols-[minmax(0,1fr)_30rem]"
    >
      <section className="flex min-h-[34rem] min-w-0 flex-col border-b xl:border-b-0 xl:border-r">
        <div className="flex min-h-16 flex-wrap items-center justify-between gap-3 border-b px-4 py-3 sm:px-6">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Document workspace</p>
            <h2 className="truncate text-lg font-semibold">Untitled SLM Evaluation</h2>
          </div>
          <Button variant="outline" className="h-9 gap-2">
            <Upload className="size-4" aria-hidden="true" />
            Upload
          </Button>
        </div>

        <div className="grid flex-1 place-items-center px-4 py-8 sm:px-6 lg:px-8">
          <div className="w-full max-w-3xl space-y-6 text-center">
            <div className="mx-auto flex size-16 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <FileText className="size-8" aria-hidden="true" />
            </div>

            <div className="space-y-2">
              <h3 className="text-2xl font-semibold">Upload an SLM or reference document</h3>
              <p className="mx-auto max-w-xl text-sm leading-6 text-muted-foreground">
                Add the document that will move through preprocessing, embedding, evaluator agents, and synthesis.
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
              <Input id="pdf-file" type="file" accept="application/pdf" onChange={handleFileChange} className="sr-only" />
            </Label>

            <div className="grid gap-4 text-left md:grid-cols-2">
              <div className="space-y-2">
                <Label>Program</Label>
                <Select value={program} onValueChange={handleProgramChange}>
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
              </div>

              <div className="space-y-2">
                <Label>Subject</Label>
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
              <Link2 className="size-4" aria-hidden="true" />
              Reference links
            </span>
            <span className="min-w-0">Syllabus and curriculum can be associated before evaluation.</span>
          </div>
          <Button variant="ghost" className="h-9 gap-2 text-primary">
            Proofread
            <CheckSquare className="size-4" aria-hidden="true" />
          </Button>
        </div>
      </section>

      <aside className="flex min-h-[34rem] flex-col bg-muted/20">
        <div className="border-b px-4 py-7 sm:px-7 sm:py-8">
          <h3 className="text-2xl font-semibold">Welcome back, Marc.</h3>
          <p className="mt-2 text-sm text-muted-foreground">Select evaluator checks and submit the document to start.</p>
        </div>

        <div className="grid gap-4 px-4 py-6 sm:px-7">
          {scanOptions.map((option) => {
            const Icon = option.icon;
            const checked = selectedChecks.includes(option.id);

            return (
              <button
                key={option.id}
                type="button"
                onClick={() => toggleCheck(option.id)}
                className={cn(
                  'flex min-h-24 items-center gap-4 rounded-lg border px-5 text-left shadow-sm transition-colors',
                  checked
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-950 hover:bg-emerald-100'
                    : 'border-border bg-card text-foreground hover:bg-muted/40'
                )}
              >
                <Icon className={cn('size-8 shrink-0', checked ? 'text-emerald-700' : 'text-foreground')} aria-hidden="true" />
                <span className="min-w-0 flex-1">
                  <span className="block text-base font-semibold">{option.title}</span>
                  <span className={cn('block text-sm leading-5', checked ? 'text-emerald-800/75' : 'text-muted-foreground')}>
                    {option.description}
                  </span>
                </span>
                <span
                  className={cn(
                    'flex size-6 shrink-0 items-center justify-center rounded-md border',
                    checked
                      ? 'border-emerald-600 bg-emerald-600 text-white'
                      : 'border-foreground/30 bg-background text-transparent'
                  )}
                  aria-hidden="true"
                >
                  {checked ? <Check className="size-4" /> : null}
                </span>
              </button>
            );
          })}
        </div>

        <div className="sticky bottom-0 mt-auto border-t bg-card/95 px-4 py-4 shadow-[0_-10px_30px_rgba(0,0,0,0.04)] backdrop-blur sm:px-7">
          <div className="space-y-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Selected checks</span>
              <span className="font-medium">{selectedChecks.length} of 4</span>
            </div>
            <Button type="submit" className="h-14 w-full justify-between rounded-lg px-5 text-base">
              Start evaluation
              <ArrowRight className="size-5" aria-hidden="true" />
            </Button>
            <p className="text-center text-sm text-muted-foreground">
              Generated evaluations are advisory; human review remains authoritative.
            </p>
          </div>
        </div>
      </aside>
    </form>
  );
}
