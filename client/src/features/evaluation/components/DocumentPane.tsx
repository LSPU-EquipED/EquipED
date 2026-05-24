import { Loader2, AlertTriangle } from 'lucide-react';
import { getErrorMessage } from '@/shared/api/http';
import { Button } from '@/shared/components/ui/button';
import type { ClientDocument, ClientDocumentChunk } from '@/shared/types/documents';
import type { EvaluationFlagItem } from '../types';
import { FlagList } from './FlagList';

type DocumentTextGroup = {
  documentId: string;
  chunks: ClientDocumentChunk[];
};

type DocumentPaneProps = {
  document: ClientDocument | null | undefined;
  isLoading: boolean;
  error: unknown;
  isResolvingEval: boolean;
  submitIsPending: boolean;
  isResolveError: boolean;
  resolveError: unknown;
  refetchResolve: () => void;
  submitIsError: boolean;
  submitError: unknown;
  handleRetrySubmit: () => void;
  documentTextGroups: DocumentTextGroup[];
  selectedFlags: EvaluationFlagItem[];
  chunkMap: Map<string, ClientDocumentChunk>;
  selectedAgentLabel: string;
};

export function DocumentPane({
  document,
  isLoading,
  error,
  isResolvingEval,
  submitIsPending,
  isResolveError,
  resolveError,
  refetchResolve,
  submitIsError,
  submitError,
  handleRetrySubmit,
  documentTextGroups,
  selectedFlags,
  chunkMap,
  selectedAgentLabel,
}: DocumentPaneProps) {
  const documentSubtitle = [document?.courseTitle, document?.lessonTitle]
    .filter(Boolean)
    .join(' - ');

  return (
    <section className="min-h-0 overflow-y-auto bg-background">
      <div className="mx-auto grid max-w-3xl gap-7 px-10 py-16">
        <div className="flex items-start justify-between gap-4 border-b pb-6">
          <div>
            <h2 className="text-base font-semibold">{document?.title ?? 'Selected SLM'}</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {documentSubtitle || document?.program || 'SLM content preview'}
            </p>
          </div>
          <Button type="button" variant="outline" className="shrink-0">
            {selectedAgentLabel}
          </Button>
        </div>

        {isLoading || isResolvingEval || submitIsPending ? (
          <div className="flex items-center gap-3 rounded-lg border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            {isResolvingEval
              ? 'Checking for existing evaluation…'
              : submitIsPending
                ? 'Submitting new evaluation…'
                : 'Loading SLM content...'}
          </div>
        ) : null}

        {error ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {getErrorMessage(error, 'Unable to load the selected document.')}
          </div>
        ) : null}

        {isResolveError && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              <div className="flex-1">
                <p className="font-medium">{getErrorMessage(resolveError, 'Failed to start evaluation.')}</p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-2"
                  onClick={() => refetchResolve()}
                >
                  Retry
                </Button>
              </div>
            </div>
          </div>
        )}

        {submitIsError && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              <div className="flex-1">
                <p className="font-medium">{getErrorMessage(submitError, 'Failed to start evaluation.')}</p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-2"
                  onClick={handleRetrySubmit}
                >
                  Retry
                </Button>
              </div>
            </div>
          </div>
        )}

        {!isLoading && !error ? (
          <article className="space-y-6 text-xl leading-9 text-muted-foreground">
            {documentTextGroups.length > 0 ? (
              documentTextGroups.map((group) => (
                <section key={group.documentId} className="space-y-5">
                  <div>
                    <h3 className="text-base font-semibold leading-6 text-foreground">
                      Document {group.documentId}
                    </h3>
                    <p className="text-sm leading-5 text-muted-foreground">Extracted text</p>
                  </div>
                  {group.chunks.map((chunk) => (
                    <section key={chunk.chunkId} id={`chunk-${chunk.chunkId}`} className="space-y-2 rounded-md transition-colors">
                      <p className="text-sm font-semibold leading-5 text-foreground">
                        Page {chunk.pageNumber}
                      </p>
                      {chunk.text.split(/\n{2,}/).map((paragraph, paragraphIndex) => (
                        <p key={`${chunk.chunkId}-${paragraphIndex}`}>{paragraph}</p>
                      ))}
                    </section>
                  ))}
                </section>
              ))
            ) : (
              <p>
                No extracted SLM text is available yet. The document metadata is loaded, but
                preprocessing has not produced structured content for this file.
              </p>
            )}
          </article>
        ) : null}

        <FlagList flags={selectedFlags} agentLabel={selectedAgentLabel} chunkMap={chunkMap} />
      </div>
    </section>
  );
}
