import { Outlet, useParams } from '@tanstack/react-router';
import { AlertTriangle, Loader2, Info } from 'lucide-react';
import { Separator } from '@/shared/components/ui/separator';
import { useEvaluation } from '../hooks/useEvaluationStatus';

const STATUS_MESSAGES: Record<string, string> = {
  SUBMITTED: 'Job submitted, waiting to start...',
  PREPROCESSING: 'Preprocessing document contents...',
  EMBEDDING: 'Generating vector embeddings...',
  EVALUATING: 'Running multi-agent evaluation layer...',
  SYNTHESIZING: 'Synthesizing agent reports...',
  COMPLETED: 'Evaluation completed.',
  FAILED: 'Evaluation failed.',
};

export function Scorecard() {
  const { id } = useParams({ strict: false }) as { id?: string };
  
  const { data: evaluation, isLoading, isError } = useEvaluation(id ?? '');

  if (!id) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-muted-foreground">
        No evaluation ID provided.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4 text-muted-foreground">
          <Loader2 className="size-8 animate-spin" />
          <p>Loading evaluation...</p>
        </div>
      </div>
    );
  }

  if (isError || !evaluation) {
    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4 text-destructive">
          <AlertTriangle className="size-8" />
          <p>Failed to load evaluation. It may not exist or you might not have access.</p>
        </div>
      </div>
    );
  }

  const isTerminal = evaluation.status === 'COMPLETED' || evaluation.status === 'FAILED';
  const isFailed = evaluation.status === 'FAILED';

  return (
    <section className="-mx-6 -my-7 flex h-[calc(100vh-4rem)] flex-col bg-background">
      <header className="flex min-h-24 shrink-0 items-center justify-between gap-4 border-b bg-background px-10">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.26em] text-muted-foreground">
            Evaluation Status
          </p>
          <h1 className="mt-2 truncate text-2xl font-semibold">
            Job: {evaluation.evaluation_id}
          </h1>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto p-10">
        <div className="mx-auto max-w-3xl rounded-xl border bg-card p-8 shadow-sm">
          <div className="flex items-center gap-4 border-b pb-6">
            {!isTerminal && (
              <Loader2 className="size-8 animate-spin text-primary" />
            )}
            {isTerminal && !isFailed && (
              <Info className="size-8 text-muted-foreground" />
            )}
            {isFailed && (
              <AlertTriangle className="size-8 text-destructive" />
            )}
            
            <div>
              <h2 className="text-xl font-semibold">
                {evaluation.status}
              </h2>
              <p className="text-muted-foreground mt-1">
                {STATUS_MESSAGES[evaluation.status] || 'Processing...'}
              </p>
            </div>
          </div>

          <div className="mt-6 space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="font-semibold text-muted-foreground">Target Document</p>
                <p className="mt-1 font-mono">{evaluation.document_id}</p>
              </div>
              <div>
                <p className="font-semibold text-muted-foreground">Syllabus</p>
                <p className="mt-1 font-mono">{evaluation.syllabus_id}</p>
              </div>
              <div>
                <p className="font-semibold text-muted-foreground">Curriculum</p>
                <p className="mt-1 font-mono">{evaluation.curriculum_id}</p>
              </div>
              <div>
                <p className="font-semibold text-muted-foreground">Submitted At</p>
                <p className="mt-1">{new Date(evaluation.submitted_at).toLocaleString()}</p>
              </div>
              {evaluation.completed_at && (
                <div>
                  <p className="font-semibold text-muted-foreground">Finished At</p>
                  <p className="mt-1">{new Date(evaluation.completed_at).toLocaleString()}</p>
                </div>
              )}
            </div>

            {isFailed && evaluation.error_message && (
              <>
                <Separator className="my-4" />
                <div className="rounded-md bg-destructive/10 p-4">
                  <p className="font-semibold text-destructive">Error Details</p>
                  <p className="mt-2 text-sm text-destructive/80 font-mono whitespace-pre-wrap">
                    {evaluation.error_message}
                  </p>
                </div>
              </>
            )}
          </div>
        </div>
      </main>

      <Outlet />
    </section>
  );
}
