import { useMemo, useState } from 'react';
import { CaretDown, CaretRight } from '@phosphor-icons/react';
import { Card, CardContent, cn } from '@equiped/ui';
import type { MatrixCriterionScoreItem } from '../types';

export interface SynthesisCriteriaInspectionProps {
  criteria: MatrixCriterionScoreItem[];
}

export function SynthesisCriteriaInspection({
  criteria,
}: SynthesisCriteriaInspectionProps) {
  const [expandedCriteriaKeys, setExpandedCriteriaKeys] = useState<Set<string>>(new Set());

  const allCriteriaKeys = useMemo(
    () => criteria.map((c, i) => c.criterion_id || String(i)),
    [criteria],
  );

  const toggleCriterion = (key: string) => {
    setExpandedCriteriaKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const areAllExpanded =
    allCriteriaKeys.length > 0 && allCriteriaKeys.every((key) => expandedCriteriaKeys.has(key));

  const toggleAllCriteria = () => {
    if (areAllExpanded) {
      setExpandedCriteriaKeys(new Set());
    } else {
      setExpandedCriteriaKeys(new Set(allCriteriaKeys));
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between h-6">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-text">Rubric criteria assessment</h3>
          <span className="text-xs text-text-muted">
            ({criteria.length})
          </span>
        </div>

        {criteria.length > 0 && (
          <button
            type="button"
            onClick={toggleAllCriteria}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-text-muted hover:text-text cursor-pointer transition-colors"
          >
            <CaretDown
              className={cn(
                'size-3.5 transition-transform duration-200',
                areAllExpanded && 'rotate-180',
              )}
              aria-hidden="true"
            />
            <span>{areAllExpanded ? 'Collapse All' : 'Expand All'}</span>
          </button>
        )}
      </div>

      {criteria.length > 0 ? (
        <div className="overflow-hidden border-y border-border bg-surface">
          {criteria.map((crit, idx) => {
            const criterionKey = crit.criterion_id || String(idx);
            const isExpanded = expandedCriteriaKeys.has(criterionKey);

            return (
              <Card
                key={criterionKey}
                className={cn(
                  'rounded-none border-0 border-b border-border shadow-none last:border-b-0 transition-colors',
                  isExpanded ? 'border-l-2 border-l-primary bg-primary-soft/15' : 'border-l-2 border-l-transparent hover:bg-surface-subtle/45',
                )}
              >
                <CardContent className="p-3.5 sm:p-4 space-y-0">
                  {/* Clickable Card Header */}
                  <div
                    onClick={() => toggleCriterion(criterionKey)}
                    className="flex items-start justify-between gap-3 cursor-pointer select-none group"
                    role="button"
                    tabIndex={0}
                    aria-expanded={isExpanded}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        toggleCriterion(criterionKey);
                      }
                    }}
                  >
                    <div className="flex items-start gap-2.5 min-w-0">
                      <CaretRight
                        className={cn(
                          'size-4 text-text-muted mt-0.5 shrink-0 transition-transform duration-200',
                          isExpanded && 'rotate-90 text-primary',
                        )}
                        aria-hidden="true"
                      />
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="shrink-0 rounded-xs border border-border bg-surface-subtle px-1.5 py-0.5 font-mono text-[11px] font-semibold text-text-muted">
                            {crit.criterion_id}
                          </span>
                          <h4 className="truncate text-sm font-semibold text-text transition-colors group-hover:text-primary">
                            {crit.criterion_text}
                          </h4>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-xs text-text-muted font-medium hidden sm:inline">Score:</span>
                      <span className="inline-flex items-center px-2 py-0.5 rounded-xs font-bold text-xs bg-primary-soft text-primary border border-primary/20 tabular-nums">
                        {crit.score} / 4
                      </span>
                    </div>
                  </div>

                  {/* Collapsible Details Body */}
                  <div
                    className={cn(
                      'animate-ledger-collapse',
                      isExpanded
                        ? 'animate-ledger-collapse-expanded'
                        : 'animate-ledger-collapse-collapsed',
                    )}
                    aria-hidden={!isExpanded}
                  >
                    <div className="min-h-0 overflow-hidden">
                      <div className="pt-3 mt-3 border-t border-border/60 space-y-2.5 pl-6 sm:pl-6.5">
                        {crit.description ? (
                          <p className="text-xs text-text-muted leading-relaxed">{crit.description}</p>
                        ) : null}

                        {crit.justification ? (
                          <div className="text-xs text-text space-y-1">
                            <span className="block text-xs font-semibold text-text-muted">Justification:</span>
                            <p className="leading-relaxed bg-surface-subtle/50 p-2.5 rounded-xs border border-border/40">
                              {crit.justification}
                            </p>
                          </div>
                        ) : null}

                        {crit.evidence ? (
                          <div className="text-xs text-text space-y-1">
                            <span className="block text-xs font-semibold text-text-muted">Evidence excerpt:</span>
                            <blockquote className="border-l-2 border-primary/50 bg-surface-subtle/30 py-1 pl-3 font-mono text-xs italic text-text-muted">
                              "{crit.evidence}"
                            </blockquote>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : (
        <div className="p-8 text-center border border-dashed border-border rounded-md bg-surface-subtle/30 text-text-muted text-xs">
          No specific criteria items recorded for this pillar yet.
        </div>
      )}
    </div>
  );
}
