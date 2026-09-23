import { Fragment, useRef } from 'react';
import { Link } from '@tanstack/react-router';
import {
  CaretRight,
  FilePdf,
  User,
  Warning,
} from '@phosphor-icons/react';
import { Badge, CollapsibleRow, TABLE_STYLES, cn, getEvaluationStatusVariant } from '@equiped/ui';
import type { MonitoringMatrixRow as MonitoringMatrixRowType } from '../types';
import {
  domainShortLabel,
  formatDomainScore,
  formatProgressStatus,
  formatRevisionContext,
  getCompletedDomainCount,
  getRatingVariant,
  isDomainBlockEvaluated,
  TARGET_DOMAIN_ORDER,
} from '../utils';

export interface MonitoringMatrixRowProps {
  row: MonitoringMatrixRowType;
  isExpanded: boolean;
  onToggle: () => void;
}

export function MonitoringMatrixRow({
  row,
  isExpanded,
  onToggle,
}: MonitoringMatrixRowProps) {
  const disclosureButtonRef = useRef<HTMLButtonElement | null>(null);

  const rowKey = row.evaluation_id ?? row.matrix_id;
  const drawerId = `collapsible-drawer-${rowKey}`;

  const handleToggle = () => {
    if (isExpanded) {
      const button = disclosureButtonRef.current;
      const drawer = document.getElementById(drawerId);
      if (
        drawer &&
        document.activeElement &&
        drawer.contains(document.activeElement) &&
        button
      ) {
        button.focus();
      }
    }
    onToggle();
  };

  return (
    <Fragment>
      <tr
        className={cn(
          TABLE_STYLES.tr,
          'hover:bg-surface-subtle transition-colors group',
          isExpanded && 'bg-surface-subtle/40 border-b-transparent',
        )}
      >
        {/* Expand / Collapse Caret Toggle */}
        <td className="w-10 text-center py-3 pl-4 pr-1">
          <button
            type="button"
            ref={disclosureButtonRef}
            onClick={handleToggle}
            aria-expanded={isExpanded}
            aria-controls={drawerId}
            aria-label={`${isExpanded ? 'Collapse' : 'Expand'} details for ${row.document_title || 'module'}`}
            className="inline-flex size-7 items-center justify-center rounded-xs text-text-muted hover:text-text hover:bg-surface-subtle transition-colors cursor-pointer"
          >
            <CaretRight
              className={cn(
                'size-3.5 transition-transform duration-150',
                isExpanded && 'rotate-90 text-primary',
              )}
              aria-hidden="true"
            />
          </button>
        </td>

        {/* SLM Title & Faculty Member & Inline Program Badge */}
        <td className={cn(TABLE_STYLES.td, 'min-w-[18rem] sm:min-w-[22rem]')}>
          <div className="flex items-start gap-2.5">
            <FilePdf className="size-4 text-primary shrink-0 mt-0.5" aria-hidden="true" />
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  to="/admin/synthesis/$documentId"
                  params={{ documentId: row.document_id }}
                  className="truncate font-semibold text-sm text-text hover:text-primary transition-colors cursor-pointer"
                  title={row.document_title || 'Untitled SLM'}
                  data-testid={`module-title-link-${row.document_id}`}
                >
                  {row.document_title || 'Untitled SLM'}
                </Link>
                {row.program && (
                  <span className="inline-flex items-center rounded-xs border border-border bg-surface-subtle px-1.5 py-0.2 font-mono text-[10px] font-semibold text-text select-none shrink-0">
                    {row.program}
                  </span>
                )}
              </div>
              {row.faculty_name ? (
                <div className="flex items-center gap-1 text-[11px] font-normal text-text-muted truncate mt-0.5">
                  <User className="size-3 text-text-muted shrink-0" aria-hidden="true" />
                  <span>Faculty: {row.faculty_name}</span>
                </div>
              ) : null}
            </div>
          </div>
        </td>

        {/* Evaluation Status */}
        <td className={cn(TABLE_STYLES.td, 'w-44 min-w-[11rem] whitespace-nowrap')}>
          <Badge variant={getEvaluationStatusVariant(row.evaluation_status)} withDot className="whitespace-nowrap">
            {formatProgressStatus(row.evaluation_status, row.domain_scores)}
          </Badge>
        </td>

        {/* Rating */}
        <td className={cn(TABLE_STYLES.td, 'w-36 min-w-[8rem] whitespace-nowrap')}>
          {row.adjectival_rating ? (
            <Badge variant={getRatingVariant(row.adjectival_rating)}>
              {row.adjectival_rating}
            </Badge>
          ) : (
            <span className="text-text-muted font-medium select-none">—</span>
          )}
        </td>

        {/* Actions / Drilldown */}
        <td className={cn(TABLE_STYLES.td, 'text-right w-36 min-w-[8.5rem] whitespace-nowrap pr-6')}>
          <Link
            to="/admin/synthesis/$documentId"
            params={{ documentId: row.document_id }}
            className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:text-primary-strong transition-colors group/action select-none cursor-pointer"
            onClick={(e) => {
              e.stopPropagation();
            }}
            title="View Master Synthesis Scorecard"
            data-testid={`view-synthesis-${row.document_id}`}
          >
            <span>View Synthesis</span>
            <CaretRight className="size-3.5 transition-transform group-hover/action:translate-x-0.5" aria-hidden="true" />
          </Link>
        </td>
      </tr>

      {/* Collapsible Detail Sub-row */}
      <CollapsibleRow
        id={drawerId}
        isExpanded={isExpanded}
        colSpan={5}
        innerClassName="space-y-3.5 px-6 py-4 pl-12 sm:pl-14"
      >
        {/* Domain Evaluation Multi-Pillar Breakdown */}
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wider text-text-muted mb-2">
            Multi-Pillar Domain Breakdown
          </p>
          <div
            className="grid grid-cols-2 sm:grid-cols-4 gap-2.5"
            aria-label={`Domain completion: ${getCompletedDomainCount(row.domain_scores)} of 4 domains evaluated`}
          >
            {TARGET_DOMAIN_ORDER.map((domainId) => {
              const block = row.domain_scores?.[domainId];
              const isEvaluated = isDomainBlockEvaluated(block);
              const normalizedStatus = typeof block?.status === 'string' ? block.status.toUpperCase() : '';
              const isFailed = !isEvaluated && (normalizedStatus === 'ERROR' || normalizedStatus === 'FAILED');

              let borderBgClass = 'border-border/60 bg-surface/50 text-text-muted';
              if (isEvaluated) {
                borderBgClass = 'border-success/30 bg-surface text-text';
              } else if (isFailed) {
                borderBgClass = 'border-destructive/30 bg-surface text-text';
              }

              return (
                <div
                  key={domainId}
                  className={cn(
                    'rounded-sm border p-2.5 flex flex-col justify-between transition-colors',
                    borderBgClass,
                  )}
                >
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="font-semibold text-text">
                      {domainShortLabel(domainId)}
                    </span>
                    {isEvaluated ? (
                      <span className="text-[10px] font-bold text-success bg-success-soft px-1.5 py-0.5 rounded-xs">
                        Evaluated
                      </span>
                    ) : isFailed ? (
                      <span className="text-[10px] font-bold text-destructive bg-destructive-soft px-1.5 py-0.5 rounded-xs">
                        Failed
                      </span>
                    ) : (
                      <span className="text-[10px] font-medium text-text-muted/60 bg-surface-subtle px-1.5 py-0.5 rounded-xs">
                        Pending
                      </span>
                    )}
                  </div>
                  <div className="flex items-baseline justify-between mt-1">
                    <span className="text-sm font-bold tabular-nums text-text">
                      {isEvaluated && block
                        ? `${domainShortLabel(domainId)} ${formatDomainScore(block.subtotal)}`
                        : isFailed
                          ? `${domainShortLabel(domainId)} Failed`
                          : `${domainShortLabel(domainId)} Pending`}
                    </span>
                    {isEvaluated && block && block.max_score != null && Number.isFinite(block.max_score) ? (
                      <span className="text-[11px] text-text-muted">
                        / {formatDomainScore(block.max_score)}
                      </span>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Secondary Metadata Strip */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-border/60 text-xs text-text-muted">
          <div className="flex flex-wrap items-center gap-5">
            <div className="flex items-center gap-1.5">
              <span className="font-semibold text-text">Form Revision:</span>
              <span className="font-mono text-text-muted">
                {formatRevisionContext(row.domain_scores)}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="font-semibold text-text">Last Updated:</span>
              <span>{new Date(row.last_updated).toLocaleDateString()}</span>
            </div>
            {row.flag_count > 0 && (
              <div className="flex items-center gap-1 text-warning font-semibold">
                <Warning className="size-3.5" aria-hidden="true" />
                <span>{row.flag_count} issue flag{row.flag_count > 1 ? 's' : ''}</span>
              </div>
            )}
          </div>

          <Link
            to="/admin/synthesis/$documentId"
            params={{ documentId: row.document_id }}
            className="inline-flex items-center gap-1 font-semibold text-primary hover:text-primary-strong transition-colors text-xs"
            onClick={(e) => e.stopPropagation()}
          >
            <span>Open full scorecard</span>
            <CaretRight className="size-3" aria-hidden="true" />
          </Link>
        </div>
      </CollapsibleRow>
    </Fragment>
  );
}
