import { useState, type PointerEvent } from 'react';
import { useParams } from '@tanstack/react-router';
import { useEvaluationPageState } from '../hooks/useEvaluationPageState';
import { EvaluationHeader } from './EvaluationHeader';
import { DocumentPane } from './DocumentPane';
import { ScoreDashboard } from './ScoreDashboard';

type AgentId = 'coordinator' | 'sme' | 'gad' | 'itso';

const agents = [
  { id: 'coordinator' as AgentId, name: 'Program Coordinator' },
  { id: 'sme' as AgentId, name: 'Subject Matter Expert (SME)' },
  { id: 'gad' as AgentId, name: 'GAD Unit' },
  { id: 'itso' as AgentId, name: 'ITSO' },
];

export function EvaluationInterface() {
  const { documentId } = useParams({ strict: false }) as { documentId?: string };
  const [selectedAgentId, setSelectedAgentId] = useState<AgentId>('itso');
  const [leftPaneSize, setLeftPaneSize] = useState(48);

  const {
    document,
    isLoadingDocument,
    documentError,
    evaluationId,
    isResolvingEval,
    isResolveError,
    resolveError,
    refetchResolve,
    submitEvaluation,
    results,
    refetchResults,
    isResultsError,
    resultsError,
    status,
    isTerminal,
    hasResults,
    isInProgress,
    isFailedWithResults,
    handleRetryEvaluation,
    handleRetrySubmit,
    documentTextGroups,
    chunkMap,
  } = useEvaluationPageState(documentId);

  const selectedAgent = agents.find((agent) => agent.id === selectedAgentId) ?? agents[0];
  const selectedFlags = results?.flags.filter((flag) => flag.agent_id === selectedAgentId) || [];

  const handleDividerPointerDown = (event: PointerEvent<HTMLButtonElement>) => {
    const container = event.currentTarget.parentElement;

    if (!container) {
      return;
    }

    const bounds = container.getBoundingClientRect();

    const handlePointerMove = (moveEvent: globalThis.PointerEvent) => {
      const nextSize = ((moveEvent.clientX - bounds.left) / bounds.width) * 100;
      setLeftPaneSize(Math.min(64, Math.max(36, nextSize)));
    };

    const handlePointerUp = () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };

    event.currentTarget.setPointerCapture(event.pointerId);
    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
  };

  return (
    <section className="flex h-[calc(100vh-4rem)] min-h-0 flex-col bg-background">
      <EvaluationHeader
        document={document}
        selectedAgent={selectedAgent}
        results={results}
        hasResults={hasResults}
        isTerminal={isTerminal}
        evaluationId={evaluationId}
      />

      <div
        className="grid min-h-0 flex-1"
        style={{
          gridTemplateColumns: `minmax(24rem, ${leftPaneSize}fr) 0.25rem minmax(28rem, ${100 - leftPaneSize}fr)`,
        }}
      >
        <DocumentPane
          document={document}
          isLoading={isLoadingDocument}
          error={documentError}
          isResolvingEval={isResolvingEval}
          submitIsPending={!!submitEvaluation.isPending}
          isResolveError={isResolveError}
          resolveError={resolveError}
          refetchResolve={refetchResolve}
          submitIsError={!!submitEvaluation.isError}
          submitError={submitEvaluation.error}
          handleRetrySubmit={handleRetrySubmit}
          documentTextGroups={documentTextGroups}
          selectedFlags={selectedFlags}
          chunkMap={chunkMap}
          selectedAgentLabel={selectedAgent.name}
        />

        <button
          type="button"
          className="group relative min-h-0 cursor-col-resize bg-border outline-none transition-colors hover:bg-foreground/50 focus-visible:bg-foreground/50"
          onPointerDown={handleDividerPointerDown}
          aria-label="Resize document and score panels"
        >
          <span className="absolute inset-y-0 left-1/2 w-1 -translate-x-1/2" />
        </button>

        <ScoreDashboard
          status={status}
          results={results}
          isTerminal={isTerminal}
          isInProgress={isInProgress}
          isFailedWithResults={isFailedWithResults}
          isResultsError={isResultsError}
          resultsError={resultsError}
          refetchResults={refetchResults}
          handleRetryEvaluation={handleRetryEvaluation}
          isResolvingEval={isResolvingEval}
          submitIsPending={!!submitEvaluation.isPending}
          evaluationId={evaluationId}
          selectedAgentId={selectedAgentId}
          onSelectAgent={setSelectedAgentId}
        />
      </div>
    </section>
  );
}
