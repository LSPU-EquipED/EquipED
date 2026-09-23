import { useMemo } from 'react';
import { CheckCircle, Clock, Warning } from '@phosphor-icons/react';
import { Badge, getEvaluationStatusVariant } from '@equiped/ui';
import { SynthesisCriteriaInspection } from './SynthesisCriteriaInspection';
import type { EvaluationFlagItem, MasterSynthesisPillar } from '../types';
import {
  formatDomainScore,
  PILLAR_CONFIGS,
  type TargetDomainId,
} from '../utils';

export interface SpecialistInspectionPanelProps {
  activePillarId: TargetDomainId;
  pillar: MasterSynthesisPillar | undefined;
  flags?: EvaluationFlagItem[];
}

function selectActivePillarFlags(
  flags: EvaluationFlagItem[] | undefined,
  activePillarId: TargetDomainId,
  configId: string,
): EvaluationFlagItem[] {
  if (!flags) return [];
  const lowerPillarId = activePillarId.toLowerCase();
  const lowerConfigId = configId.toLowerCase();
  return flags.filter(
    (f) => {
      const agentId = f.agent_id?.toLowerCase();
      return agentId === lowerPillarId || agentId === lowerConfigId;
    },
  );
}

export function SpecialistInspectionPanel({
  activePillarId,
  pillar,
  flags,
}: SpecialistInspectionPanelProps) {
  const pillarConfig = PILLAR_CONFIGS[activePillarId];

  const currentCriteria = useMemo(() => pillar?.criteria ?? [], [pillar?.criteria]);

  const activePillarFlags = useMemo(
    () => selectActivePillarFlags(flags, activePillarId, pillarConfig.id),
    [flags, activePillarId, pillarConfig.id],
  );

  return (
    <section
      role="tabpanel"
      id={`tab-content-${activePillarId}`}
      aria-labelledby={`pillar-tab-${activePillarId}`}
      tabIndex={0}
      className="min-w-0 space-y-4 focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
      data-testid={`tab-content-${activePillarId}`}
    >
      {/* Active specialist overview */}
      <section
        className="overflow-hidden rounded-md border border-border border-l-2 border-l-primary bg-surface"
        aria-label="Active specialist overview"
      >
        <div className="grid gap-6 p-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:p-6">
          <div className="min-w-0">
            <p className="text-xs font-semibold text-text-muted">Specialist review</p>
            <h2 className="mt-1 truncate text-2xl font-semibold leading-tight text-text">
              {pillarConfig.label}
            </h2>
            <p className="mt-1.5 text-sm text-text-muted">{pillarConfig.roleTitle}</p>
          </div>
          <div className="flex items-end gap-3 sm:justify-end">
            <div>
              <p className="mb-1 text-right text-xs text-text-muted">Score</p>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold tabular-nums leading-none text-text sm:text-4xl">
                  {pillar?.subtotal !== null && pillar?.subtotal !== undefined
                    ? formatDomainScore(pillar.subtotal)
                    : '—'}
                </span>
                <span className="text-base font-semibold text-text-muted">/ 4.00</span>
              </div>
            </div>
            {pillar?.status?.toUpperCase() !== 'COMPLETED' ? (
              <div className="pb-0.5">
                <Badge
                  variant={getEvaluationStatusVariant(pillar?.status ?? 'PENDING')}
                  className="px-2 py-1 text-xs font-semibold"
                >
                  {pillar?.status ?? 'PENDING'}
                </Badge>
              </div>
            ) : null}
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-border bg-surface-subtle/35 px-5 py-3.5 text-sm sm:px-6">
          {pillar?.evaluator ? (
            <div className="flex min-w-0 items-center gap-2">
              <CheckCircle className="size-4 shrink-0 text-success" aria-hidden="true" />
              <span className="truncate font-semibold text-text">
                Evaluated by: {pillar.evaluator.name}
              </span>
              <span className="hidden truncate text-text-muted sm:inline">
                ({pillar.evaluator.department || pillarConfig.roleTitle})
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-text-muted">
              <Clock className="size-4 shrink-0" aria-hidden="true" />
              <span className="font-semibold">Awaiting specialist review</span>
            </div>
          )}
          {pillar?.summary ? (
            <p className="max-w-xl truncate text-xs text-text-muted">{pillar.summary}</p>
          ) : null}
        </div>
      </section>

      {/* Collapsible Rubric Criteria Inspection List */}
      <SynthesisCriteriaInspection key={activePillarId} criteria={currentCriteria} />

      {/* Specialist Compliance Flags */}
      {activePillarFlags.length > 0 ? (
        <div className="space-y-3 pt-2">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-text">
            <Warning className="size-4 text-warning" />
            <span>Specialist Compliance Flags ({activePillarFlags.length})</span>
          </h3>
          <div className="space-y-2">
            {activePillarFlags.map((flag) => (
              <div
                key={flag.flag_id}
                className="p-3 rounded-xs border border-warning/30 bg-warning-soft text-xs text-warning space-y-1"
              >
                <div className="flex items-center justify-between font-bold">
                  <span>Flag ID: {flag.flag_id.slice(0, 8)}</span>
                  {flag.criterion_id ? <span>Ref: {flag.criterion_id}</span> : null}
                </div>
                <p className="text-text">{flag.message || flag.justification || 'Flagged for review'}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
