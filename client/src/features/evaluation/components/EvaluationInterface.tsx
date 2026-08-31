import { useState } from 'react';
import { useParams } from '@tanstack/react-router';
import { useEvaluationPageState } from '../hooks/useEvaluationPageState';
import { EvaluationHeader } from './EvaluationHeader';
import { EvaluationSetup } from './EvaluationSetup';
import { DocumentDossierPane } from './DocumentDossierPane';
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
  const [selectedAgentId, setSelectedAgentId] = useState<AgentId>('sme');

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
    isSetupRequired,
    effectiveProgram,
    detectedProgram,
    setSelectedProgram,
    submitEvaluationAction,
  } = useEvaluationPageState(documentId);

  const selectedAgent = agents.find((agent) => agent.id === selectedAgentId) ?? agents[0];
  const selectedFlags = results?.flags.filter((flag) => flag.agent_id === selectedAgentId) || [];

  return (
    <section className="flex h-[calc(100vh-4rem)] min-h-0 flex-col bg-canvas">
      <EvaluationHeader
        document={document}
        selectedAgent={selectedAgent}
        results={results}
        status={status}
        hasResults={hasResults}
        isTerminal={isTerminal}
        evaluationId={evaluationId}
      />

      {isSetupRequired ? (
        <EvaluationSetup
          document={document}
          isLoadingDocument={isLoadingDocument}
          documentError={documentError}
          selectedProgram={effectiveProgram}
          detectedProgram={detectedProgram}
          onSelectProgram={setSelectedProgram}
          isResolveError={isResolveError}
          resolveError={resolveError}
          onRetryResolve={refetchResolve}
          isSubmitting={!!submitEvaluation.isPending}
          submitError={submitEvaluation.error}
          onSubmit={submitEvaluationAction}
          onRetrySubmit={handleRetrySubmit}
        />
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[22rem_minmax(0,1fr)] xl:grid-cols-[26rem_minmax(0,1fr)]">
          {/* Left Column: SLM Module Dossier & Quoted Evidence */}
          <DocumentDossierPane
            document={document}
            selectedFlags={selectedFlags}
            selectedAgentLabel={selectedAgent.name}
            selectedAgentId={selectedAgentId}
          />

          {/* Right Column: Multi-Agent Score Dashboard */}
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
      )}
    </section>
  );
}
