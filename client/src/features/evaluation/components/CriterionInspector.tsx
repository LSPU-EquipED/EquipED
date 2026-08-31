import {
  CheckCircle,
  Clock,
  FileText,
  Quotes,
  Spinner,
  Target,
  WarningCircle,
} from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
import { cn } from '@/shared/components/utils';
import { TYPOGRAPHY } from '@/shared/constants/theme';
import { FeedbackPanel } from './FeedbackPanel';
import { cleanJustification, formatScore } from '../utils/scoreHelpers';
import type {
  CriterionScoreItem,
  DomainScoreBlock,
  EvaluationFlagItem,
  EvaluationResultsResponse,
  EvaluationStatusResponse,
} from '../types';

interface CriterionInspectorProps {
  criterion: CriterionScoreItem | null;
  selectedAgentId: string;
  domainScore: DomainScoreBlock | undefined;
  flags: EvaluationFlagItem[];
  status: EvaluationStatusResponse | undefined;
  results: EvaluationResultsResponse | undefined;
  isInProgress?: boolean;
  isTerminal?: boolean;
}

export function CriterionInspector({
  criterion,
  selectedAgentId: _selectedAgentId,
  domainScore,
  flags,
  status: _status,
  results,
  isInProgress,
  isTerminal: _isTerminal,
}: CriterionInspectorProps) {
  // If in progress
  if (isInProgress) {
    return (
      <div className="flex h-full min-h-[30rem] items-center justify-center p-8 text-center bg-canvas">
        <div className="flex flex-col items-center gap-3 rounded-md border border-border bg-surface p-8 max-w-sm">
          <Spinner className="size-8 animate-spin text-primary" aria-hidden="true" />
          <h3 className="font-bold text-text">Evaluation in Progress</h3>
          <p className="text-xs text-text-muted">
            Specialist agents are analyzing learning materials against institutional rubrics. Results will appear automatically.
          </p>
        </div>
      </div>
    );
  }

  // If no criterion selected yet
  if (!criterion) {
    return (
      <div className="flex h-full min-h-[30rem] items-center justify-center p-8 text-center bg-canvas">
        <div className="flex flex-col items-center gap-2 max-w-xs text-text-muted">
          <FileText className="size-8 text-text-muted/60" aria-hidden="true" />
          <p className="font-semibold text-text">No Criterion Selected</p>
          <p className="text-xs">
            Choose a criterion from the left panel to inspect findings, quoted evidence, and rubric standards.
          </p>
        </div>
      </div>
    );
  }

  const isPassing = criterion.score >= 3.0;
  const isWeak = criterion.score < 2.5;
  const criterionFlags = flags.filter((f) => f.criterion_id === criterion.criterion_id);

  return (
    <div className="flex flex-col h-full min-h-0 overflow-y-auto bg-canvas p-6 sm:p-8 space-y-6">
      {/* Top Header Card */}
      <div className="rounded-md border border-border bg-surface p-6 shadow-none">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1.5 min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-xs font-bold text-text-muted">
                {criterion.criterion_id}
              </span>
              {domainScore?.version != null ? (
                <Badge variant="neutral">Revision {domainScore.version}</Badge>
              ) : null}
              {domainScore?.version == null &&
                (results?.legacy_notice || domainScore?.form_snapshot_id == null) &&
                results && (
                  <Badge variant="neutral">Legacy — form snapshot unavailable</Badge>
                )}
              {criterion.is_ungrounded ? (
                <Badge variant="warning">Ungrounded</Badge>
              ) : null}
            </div>

            <h2 className="text-xl font-bold tracking-tight text-text">
              {criterion.criterion_text}
            </h2>
          </div>

          {/* Score Badge */}
          <div className="shrink-0 flex items-center gap-2">
            <span
              className={cn(
                'inline-flex items-center gap-1.5 rounded-sm px-3 py-1.5 text-sm font-bold tabular-nums border',
                isPassing
                  ? 'bg-success-soft text-success border-success/30'
                  : isWeak
                    ? 'bg-destructive-soft text-destructive border-destructive/30'
                    : 'bg-warning-soft text-warning border-warning/30',
              )}
            >
              {isPassing ? (
                <CheckCircle className="size-4" aria-hidden="true" />
              ) : (
                <WarningCircle className="size-4" aria-hidden="true" />
              )}
              <span>Score: {formatScore(criterion.score)} / 4.0</span>
            </span>
          </div>
        </div>
      </div>

      {/* Rubric Benchmark / Standard */}
      <div className="rounded-md border border-border bg-surface p-6 shadow-none space-y-2">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-text-muted">
          <Target className="size-4 text-text-muted" aria-hidden="true" />
          <span>Institutional Rubric Standard</span>
        </div>
        <p className="text-sm text-text leading-relaxed font-normal">
          {criterion.description || 'Standard institutional criterion benchmark for quality assurance.'}
        </p>
      </div>

      {/* Specialist Finding & Quoted Evidence */}
      <div className="rounded-md border border-border bg-surface p-6 shadow-none space-y-4">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-text">
          <Quotes className="size-4 text-primary" aria-hidden="true" weight="bold" />
          <span>Specialist Finding & Evidence</span>
        </div>

        {/* Quoted Passage Snippet if present */}
        {criterion.evidence ? (
          <div className="rounded-sm border border-border bg-surface-subtle p-4 text-xs text-text leading-relaxed font-mono">
            <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted block mb-1">
              Quoted from SLM Document:
            </span>
            "{criterion.evidence}"
          </div>
        ) : null}

        {/* Specialist Rationale */}
        {criterion.justification ? (
          <div className="space-y-1.5">
            <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">
              Specialist Rationale:
            </p>
            <p className="text-sm text-text leading-relaxed">
              {cleanJustification(criterion.justification)}
            </p>
          </div>
        ) : isPassing ? (
          <div className="flex items-center gap-2 text-xs text-success font-medium py-1">
            <CheckCircle className="size-4 text-success shrink-0" aria-hidden="true" />
            <span>Fully compliant — All institutional benchmark criteria verified.</span>
          </div>
        ) : null}

        {/* Specific Flag Details if any */}
        {criterionFlags.length > 0 && (
          <div className="rounded-sm border border-warning/30 bg-warning-soft/30 p-3.5 space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-bold text-warning">
              <WarningCircle className="size-4" aria-hidden="true" />
              <span>Flagged Observation ({criterionFlags.length})</span>
            </div>
            {criterionFlags.map((flag) => (
              <p key={flag.flag_id} className="text-xs text-text-muted leading-relaxed">
                {flag.justification ? cleanJustification(flag.justification) : flag.criterion_text}
              </p>
            ))}
          </div>
        )}
      </div>

      {/* Human Review & Feedback Section */}
      <div className="rounded-md border border-border bg-surface p-6 shadow-none">
        <FeedbackPanel criteria={[criterion]} />
      </div>
    </div>
  );
}
