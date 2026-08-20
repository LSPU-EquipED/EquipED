import { Link } from '@tanstack/react-router';
import { AlertCircle, ArrowRight } from 'lucide-react';
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
    <div className="rounded-sm border border-[#b91c1c]/30 bg-white overflow-hidden">
      <div className="flex items-center justify-between border-b border-[#b91c1c]/20 bg-[#b91c1c]/10 px-5 py-3">
        <div className="flex items-center gap-2">
          <AlertCircle className="size-4 text-[#b91c1c]" aria-hidden="true" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-[#b91c1c]">
            Recent Issues ({items.length})
          </h3>
        </div>
        <span className="text-[11px] font-medium text-[#b91c1c]">
          Resolve recent document processing or evaluation failures
        </span>
      </div>

      <div className="divide-y divide-slate-100">
        {items.map((item) => (
          <div
            key={item.id}
            className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 hover:bg-slate-50/60 transition-colors"
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="inline-flex rounded-sm bg-[#b91c1c]/10 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[#b91c1c]">
                  {item.type === 'document_failed' ? 'Processing Failed' : 'Evaluation Failed'}
                </span>
                <span className="text-xs text-slate-500 font-medium">
                  {formatDateTime(item.timestamp)}
                </span>
              </div>
              <p className="mt-1 text-sm font-semibold text-slate-900 truncate">{item.title}</p>
              <p className="text-xs text-slate-600 mt-0.5">{item.detail}</p>
            </div>

            <Link
              to={item.targetUrl}
              className="inline-flex h-8 items-center justify-center gap-1.5 rounded-sm border border-slate-200 bg-white px-3 text-xs font-bold uppercase tracking-wider text-slate-700 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87] shrink-0 transition-colors"
            >
              <span>{item.actionLabel}</span>
              <ArrowRight className="size-3 text-slate-500" aria-hidden="true" />
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}
