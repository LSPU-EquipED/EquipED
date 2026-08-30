import { Link } from '@tanstack/react-router';
import { ArrowRight, WarningCircle } from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
import { TYPOGRAPHY } from '@/shared/constants/theme';
import type { AttentionItem } from '../types';
import { formatDateTime } from '../utils/homeData';
interface AttentionLedgerProps {
  items: AttentionItem[];
}

export function AttentionLedger({ items }: AttentionLedgerProps) {
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="rounded-md border border-destructive/30 bg-surface overflow-hidden">
      <div className="flex items-center justify-between border-b border-destructive/20 bg-destructive-soft px-5 py-3">
        <div className="flex items-center gap-2">
          <WarningCircle className="size-4 text-destructive" aria-hidden="true" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-destructive">
            Recent Issues ({items.length})
          </h3>
        </div>
        <span className="text-[11px] font-medium text-destructive">
          Resolve recent document processing or evaluation failures
        </span>
      </div>

      <div className="divide-y divide-border">
        {items.map((item) => (
          <div
            key={item.id}
            className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 hover:bg-surface-subtle/70 transition-colors"
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <Badge variant="destructive">
                  {item.type === 'document_failed' ? 'Processing Failed' : 'Evaluation Failed'}
                </Badge>
                <span className="text-xs text-text-muted font-medium tabular-nums">
                  {formatDateTime(item.timestamp)}
                </span>
              </div>
              <p className="mt-1 text-sm font-semibold text-text truncate">{item.title}</p>
              <p className="text-xs text-text-muted mt-0.5">{item.detail}</p>
            </div>

            <Link
              to={item.targetUrl}
              className="inline-flex h-8 items-center justify-center gap-1.5 rounded-sm border border-border bg-surface px-3 text-xs font-semibold uppercase tracking-wider text-text hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring shrink-0 transition-colors"
            >
              <span>{item.actionLabel}</span>
              <ArrowRight className="size-3 text-text-muted" aria-hidden="true" />
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}
