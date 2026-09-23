import { useMemo, useRef } from 'react';
import { Certificate, CheckCircle, Clock } from '@phosphor-icons/react';
import { Badge, cn } from '@equiped/ui';
import type { MasterSynthesisDetailResponse } from '../types';
import {
  formatDomainScore,
  formatPillarWeight,
  getRatingVariant,
  PILLAR_CONFIGS,
  TARGET_DOMAIN_ORDER,
  type TargetDomainId,
} from '../utils';

export interface SynthesisOverviewRailProps {
  data: MasterSynthesisDetailResponse;
  activePillarId: TargetDomainId;
  onSelectPillar: (pillarId: TargetDomainId) => void;
}

export function SynthesisOverviewRail({
  data,
  activePillarId,
  onSelectPillar,
}: SynthesisOverviewRailProps) {
  const tabRefs = useRef<Record<TargetDomainId, HTMLButtonElement | null>>({
    sme: null,
    coordinator: null,
    gad: null,
    itso: null,
  });

  const completedPillarsCount = useMemo(() => {
    const pillars = data.pillars;
    if (!pillars) return 0;
    return TARGET_DOMAIN_ORDER.filter((key) => {
      const p = pillars[key];
      return p && (p.status === 'COMPLETED' || (p.subtotal !== null && p.subtotal !== undefined));
    }).length;
  }, [data.pillars]);

  const handleKeyDownTab = (event: React.KeyboardEvent, currentDomain: TargetDomainId) => {
    const currentIndex = TARGET_DOMAIN_ORDER.indexOf(currentDomain);
    let nextIndex: number;

    switch (event.key) {
      case 'ArrowDown':
      case 'ArrowRight':
        event.preventDefault();
        nextIndex = (currentIndex + 1) % TARGET_DOMAIN_ORDER.length;
        break;
      case 'ArrowUp':
      case 'ArrowLeft':
        event.preventDefault();
        nextIndex = (currentIndex - 1 + TARGET_DOMAIN_ORDER.length) % TARGET_DOMAIN_ORDER.length;
        break;
      case 'Home':
        event.preventDefault();
        nextIndex = 0;
        break;
      case 'End':
        event.preventDefault();
        nextIndex = TARGET_DOMAIN_ORDER.length - 1;
        break;
      default:
        return;
    }

    const nextDomain = TARGET_DOMAIN_ORDER[nextIndex];
    onSelectPillar(nextDomain);
    tabRefs.current[nextDomain]?.focus();
  };

  return (
    <aside className="min-w-0 space-y-4 lg:sticky lg:top-4 lg:self-start" aria-label="Synthesis overview and pillar navigation">
      {/* 1. Master synthesized score */}
      <section className="overflow-hidden rounded-md border border-border bg-surface" data-testid="composite-score-banner">
        <div className="p-5 sm:p-6">
          <div className="flex items-start justify-between gap-5">
            <div>
              <p className="text-sm font-semibold text-text-muted">Overall weighted score</p>
              <div className="mt-2 flex items-baseline gap-2.5">
                <span className="text-3xl font-bold leading-none text-text tabular-nums sm:text-4xl">
                  {data.synthesized_score !== null && data.synthesized_score !== undefined
                    ? `${formatDomainScore(data.synthesized_score)}%`
                    : '—'}
                </span>
              </div>
              <p className="mt-2 text-xs text-text-muted">Weighted specialist scores, expressed as a percentage.</p>
            </div>
            {data.adjectival_rating ? (
              <div className="shrink-0 text-right">
                <p className="text-xs text-text-muted">Overall rating</p>
                <Badge variant={getRatingVariant(data.adjectival_rating)} className="mt-1.5 px-2.5 py-1 text-xs font-semibold">
                  {data.adjectival_rating}
                </Badge>
              </div>
            ) : null}
          </div>
        </div>

        <div className="border-t border-border bg-surface-subtle/40 px-5 py-3.5 sm:px-6">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-text">Pillar convergence</p>
              <p className="mt-0.5 text-xs text-text-muted">
                {completedPillarsCount === 4 ? 'All specialists converged' : `${4 - completedPillarsCount} desk(s) pending`}
              </p>
            </div>
            <span
              className={cn(
                'shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold',
                completedPillarsCount === 4
                  ? 'border border-success/30 bg-success-soft text-success'
                  : 'border border-warning/30 bg-warning-soft text-warning',
              )}
              data-testid="pillar-progress-pill"
            >
              {completedPillarsCount}/4 Pillars Complete
            </span>
          </div>
          <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-border">
            <div
              className={cn(
                'h-full transition-all duration-500',
                completedPillarsCount === 4 ? 'bg-success' : 'bg-primary',
              )}
              style={{ width: `${(completedPillarsCount / 4) * 100}%` }}
            />
          </div>
        </div>
      </section>

      <section
        className={cn(
          'overflow-hidden rounded-md border border-border bg-surface transition-colors',
          data.can_certify ? 'border-primary/50' : 'border-border',
        )}
        data-testid="accreditation-signatory-block"
      >
        <div className={cn('flex items-start gap-3 p-5', data.can_certify ? 'bg-primary-soft/25' : 'bg-surface-subtle/45')}>
          <div
            className={cn(
              'flex size-10 shrink-0 items-center justify-center rounded-sm border',
              data.can_certify
                ? 'border-primary/30 bg-surface text-primary'
                : 'border-border bg-surface text-text-muted',
            )}
          >
            <Certificate className="size-4" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-start justify-between gap-x-2 gap-y-1">
              <h2 className="text-lg font-semibold leading-tight text-text">Accreditation clearance</h2>
              <Badge
                variant={data.can_certify ? 'info' : 'neutral'}
                withDot
                className="px-2 py-1 text-xs font-semibold"
              >
                {data.can_certify
                  ? 'Ready for Sign-off'
                  : `Pending Convergence (${completedPillarsCount}/4 Desks)`}
              </Badge>
            </div>
            <p className="mt-3 text-xs font-semibold text-text-muted">Final signatory</p>
            <p className="mt-0.5 text-sm leading-snug text-text">
              Director, Center for Instructional Development
            </p>
          </div>
        </div>
        <div className="border-t border-border bg-surface p-3">
          <div
            className={cn(
              'flex h-10 w-full items-center justify-center gap-1.5 rounded-xs border px-3 text-xs font-semibold',
              data.can_certify
                ? 'border-primary/30 bg-primary-soft/40 text-primary'
                : 'border-border bg-surface-subtle text-text-muted',
            )}
            data-testid="certify-readiness-indicator"
          >
            <Certificate className="size-3.5" aria-hidden="true" />
            <span>
              {data.can_certify
                ? 'Accreditation Sign-off Ready (Read-only)'
                : 'Awaiting 4/4 Verification'}
            </span>
          </div>
        </div>
      </section>

      {/* 2. 4-Pillar Interactive Selection Rail */}
      <div className="space-y-2" data-testid="four-pillar-executive-strip" aria-label="Specialist Review Desks">
        <div className="flex items-center justify-between px-1 h-6">
          <span className="text-xs font-semibold text-text-muted" id="specialist-desks-label">
            Specialist desks
          </span>
        </div>

        <div
          className="overflow-hidden border-y border-border bg-surface"
          role="tablist"
          aria-orientation="vertical"
          aria-labelledby="specialist-desks-label"
        >
          {TARGET_DOMAIN_ORDER.map((domainId) => {
            const cfg = PILLAR_CONFIGS[domainId];
            const pillar = data.pillars?.[domainId];
            const isSelected = activePillarId === domainId;
            const evaluator = pillar?.evaluator;
            const isEvaluated = pillar?.subtotal !== null && pillar?.subtotal !== undefined;
            const weightLabel = formatPillarWeight(pillar?.weight);

            return (
              <button
                key={domainId}
                ref={(el) => {
                  tabRefs.current[domainId] = el;
                }}
                type="button"
                role="tab"
                id={`pillar-tab-${domainId}`}
                aria-selected={isSelected}
                aria-controls={`tab-content-${domainId}`}
                tabIndex={isSelected ? 0 : -1}
                onClick={() => onSelectPillar(domainId)}
                onKeyDown={(event) => handleKeyDownTab(event, domainId)}
                className={cn(
                  'group relative flex w-full cursor-pointer flex-col gap-2 border-b border-border px-3 py-3 text-left transition-colors last:border-b-0 select-none focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-[-2px]',
                  isSelected
                    ? 'border-l-2 border-l-primary bg-primary-soft/45 pl-2.5'
                    : 'border-l-2 border-l-transparent hover:bg-surface-subtle/60',
                )}
                data-testid={`pillar-card-${domainId}`}
                data-tab-button={`tab-button-${domainId}`}
              >
                {/* Header: Title & Weight */}
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="truncate text-sm font-semibold text-text" title={cfg.label}>
                        {cfg.label}
                      </span>
                      <span className="shrink-0 text-xs text-text-muted">
                        {weightLabel} weight
                      </span>
                    </div>
                  </div>

                  <div className="text-right shrink-0">
                    <span className="text-base font-semibold tabular-nums text-text">
                      {isEvaluated ? formatDomainScore(pillar.subtotal) : '—'}
                    </span>
                    <span className="text-xs text-text-muted"> / 4.00</span>
                  </div>
                </div>

                {/* Evaluator Attribution Signature Chip */}
                <div className="pt-1">
                  {evaluator && evaluator.name ? (
                    <div
                      className="flex items-center gap-1.5 truncate text-xs font-medium text-text"
                      data-testid={`evaluator-chip-${domainId}`}
                    >
                      <CheckCircle className="size-3.5 text-success shrink-0" aria-hidden="true" />
                      <span className="truncate">Evaluated by: {evaluator.name}</span>
                    </div>
                  ) : (
                    <div
                      className="flex items-center gap-1.5 text-xs font-medium text-text-muted"
                      data-testid={`awaiting-review-${domainId}`}
                    >
                      <Clock className="size-3.5 text-text-muted shrink-0" aria-hidden="true" />
                      <span>Awaiting Review</span>
                    </div>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </aside>
  );
}
