import { BookOpen, CheckCircle, FileText, GraduationCap, ShieldCheck, Warning } from '@phosphor-icons/react';
import type { StorageRepositoryMetrics } from '../hooks/useSlmStorage';
import type { DocumentStats } from '@/shared/types/documents';

interface StorageMetricsStripProps {
  metrics: StorageRepositoryMetrics;
  stats: DocumentStats;
  isLoading: boolean;
}

export function StorageMetricsStrip({ metrics, stats, isLoading }: StorageMetricsStripProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-20 rounded-md border border-border bg-surface p-4 animate-pulse"
          />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
      {/* 1. Total Modules Card */}
      <div className="rounded-md border border-border bg-surface p-4 flex items-center justify-between gap-3 shadow-none">
        <div className="space-y-0.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
            Course Modules
          </span>
          <p className="text-xl font-bold text-text tabular-nums">
            {metrics.totalModules} <span className="text-xs font-normal text-text-muted">SLMs</span>
          </p>
        </div>
        <div className="flex size-9 items-center justify-center rounded-sm bg-primary/10 text-primary border border-primary/20 shrink-0">
          <BookOpen className="size-4.5" aria-hidden="true" />
        </div>
      </div>

      {/* 2. Indexed Content Card */}
      <div className="rounded-md border border-border bg-surface p-4 flex items-center justify-between gap-3 shadow-none">
        <div className="space-y-0.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
            Indexed Content
          </span>
          <p className="text-xl font-bold text-text tabular-nums">
            {metrics.totalIndexedPages} <span className="text-xs font-normal text-text-muted">Pages</span>
          </p>
          <span className="text-[10px] text-text-muted font-medium block">
            {metrics.ocrVerifiedCount > 0 ? `${metrics.ocrVerifiedCount} with OCR text` : 'Native PDF text'}
          </span>
        </div>
        <div className="flex size-9 items-center justify-center rounded-sm bg-info/10 text-info border border-info/20 shrink-0">
          <FileText className="size-4.5" aria-hidden="true" />
        </div>
      </div>

      {/* 3. Program Balance Card */}
      <div className="rounded-md border border-border bg-surface p-4 flex items-center justify-between gap-3 shadow-none">
        <div className="space-y-0.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
            Programs
          </span>
          <p className="text-sm font-bold text-text tabular-nums pt-0.5">
            {metrics.bscsCount} <span className="text-xs font-normal text-text-muted">BSCS</span> · {metrics.bsInfoTechCount} <span className="text-xs font-normal text-text-muted">BSInfoTech</span>
          </p>
          <span className="text-[10px] text-text-muted font-medium block">
            LSPU SCC Curricula
          </span>
        </div>
        <div className="flex size-9 items-center justify-center rounded-sm bg-primary-soft text-primary border border-primary/20 shrink-0">
          <GraduationCap className="size-4.5" aria-hidden="true" />
        </div>
      </div>

      {/* 4. Ingestion Health Card */}
      <div className="rounded-md border border-border bg-surface p-4 flex items-center justify-between gap-3 shadow-none">
        <div className="space-y-0.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
            Ingestion Health
          </span>
          <div className="flex items-center gap-2 pt-0.5">
            <span className="inline-flex items-center gap-1 text-xs font-bold text-success tabular-nums">
              <CheckCircle className="size-3.5" />
              {stats.ready} Ready
            </span>
            {stats.processing > 0 && (
              <span className="text-xs font-bold text-info tabular-nums">
                · {stats.processing} Parsing
              </span>
            )}
            {stats.failed > 0 && (
              <span className="text-xs font-bold text-destructive tabular-nums">
                · {stats.failed} Failed
              </span>
            )}
          </div>
          <span className="text-[10px] text-text-muted font-medium block">
            Storage Integrity Verified
          </span>
        </div>
        <div className="flex size-9 items-center justify-center rounded-sm bg-success/10 text-success border border-success/20 shrink-0">
          <ShieldCheck className="size-4.5" aria-hidden="true" />
        </div>
      </div>
    </div>
  );
}
