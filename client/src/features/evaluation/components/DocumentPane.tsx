import { Loader2, AlertTriangle } from 'lucide-react';
import { getErrorMessage } from '@/shared/api/http';
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
    <section className="min-h-0 overflow-y-auto bg-white">
      <div className="mx-auto grid max-w-3xl gap-7 px-10 py-16">
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 pb-6">
          <div>
            <h2 className="text-base font-bold text-slate-900">{document?.title ?? 'Selected SLM'}</h2>
            <p className="mt-1.5 text-xs font-medium text-slate-500">
              {documentSubtitle || document?.program || 'SLM content preview'}
            </p>
          </div>
          <button
            type="button"
            className="shrink-0 inline-flex h-9 items-center justify-center border border-slate-200 hover:bg-slate-50 text-slate-700 px-3 rounded-sm text-xs font-semibold tracking-wide uppercase transition-colors focus:outline-none focus:ring-2 focus:ring-slate-200"
          >
            {selectedAgentLabel}
          </button>
        </div>

        {isLoading || isResolvingEval || submitIsPending ? (
          <div className="flex items-center gap-3 rounded-sm border border-slate-200 bg-slate-50 px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
            <Loader2 className="size-4 animate-spin text-[#1b3b87]" aria-hidden="true" />
            {isResolvingEval
              ? 'Checking for existing evaluation…'
              : submitIsPending
                ? 'Submitting new evaluation…'
                : 'Loading SLM content...'}
          </div>
        ) : null}

        {error ? (
          <div className="rounded-sm border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 font-semibold">
            {getErrorMessage(error, 'Unable to load the selected document.')}
          </div>
        ) : null}

        {isResolveError && (
          <div className="rounded-sm border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 font-semibold">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              <div className="flex-1">
                <p className="font-semibold">
                  {getErrorMessage(resolveError, 'Failed to start evaluation.')}
                </p>
                <button
                  type="button"
                  className="mt-2 inline-flex h-8 items-center justify-center border border-red-200 hover:bg-red-50 text-red-700 px-3 rounded-sm text-xs font-bold tracking-wide uppercase transition-colors focus:outline-none focus:ring-2 focus:ring-red-200"
                  onClick={() => refetchResolve()}
                >
                  Retry
                </button>
              </div>
            </div>
          </div>
        )}

        {submitIsError && (
          <div className="rounded-sm border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 font-semibold">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              <div className="flex-1">
                <p className="font-semibold">
                  {getErrorMessage(submitError, 'Failed to start evaluation.')}
                </p>
                <button
                  type="button"
                  className="mt-2 inline-flex h-8 items-center justify-center border border-red-200 hover:bg-red-50 text-red-700 px-3 rounded-sm text-xs font-bold tracking-wide uppercase transition-colors focus:outline-none focus:ring-2 focus:ring-red-200"
                  onClick={handleRetrySubmit}
                >
                  Retry
                </button>
              </div>
            </div>
          </div>
        )}

        {!isLoading && !error ? (
          <article className="space-y-6 text-sm leading-relaxed text-slate-700 font-normal">
            {documentTextGroups.length > 0 ? (
              documentTextGroups.map((group) => (
                <section key={group.documentId} className="space-y-5">
                  <div className="border-b border-slate-100 pb-2">
                    <h3 className="text-sm font-semibold text-slate-800">
                      Document {group.documentId}
                    </h3>
                    <p className="text-xs font-medium text-slate-400 mt-0.5">Extracted text</p>
                  </div>
                  {group.chunks.map((chunk) => (
                    <section
                      key={chunk.chunkId}
                      id={`chunk-${chunk.chunkId}`}
                      className="space-y-2 rounded-sm transition-colors"
                    >
                      <p className="text-xs font-semibold text-slate-500">
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
