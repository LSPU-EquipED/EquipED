import { AlertCircle, CheckCircle2, X } from 'lucide-react';
import type { ValidationReport } from '../types';

interface ValidationReportCardProps {
  report: ValidationReport;
  onDismiss?: () => void;
}

export function ValidationReportCard({ report, onDismiss }: ValidationReportCardProps) {
  const isValid = report.is_valid;
  const errors = report.issues.filter((i) => i.severity === 'error');
  const warnings = report.issues.filter((i) => i.severity === 'warning');
  const infos = report.issues.filter((i) => i.severity === 'info');

  return (
    <section
      aria-label="Validation Report"
      className={`rounded-sm border p-4 ${
        isValid
          ? 'border-success/40 bg-success-soft text-text'
          : 'border-destructive/40 bg-destructive-soft text-text'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          {isValid ? (
            <CheckCircle2 className="size-5 shrink-0 text-success mt-0.5" aria-hidden="true" />
          ) : (
            <AlertCircle className="size-5 shrink-0 text-destructive mt-0.5" aria-hidden="true" />
          )}
          <div>
            <h3 className="text-sm font-bold tracking-tight text-text">
              {isValid
                ? 'Form Conforms to Agent Capability Manifest'
                : `Validation Issues Detected (${report.issues.length})`}
            </h3>
            <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-text-muted font-semibold uppercase tracking-wider tabular-nums">
              <span>Criteria Count: {report.criteria_count}</span>
              <span>·</span>
              <span>
                Estimated Prompt Budget: {report.estimated_prompt_chars.toLocaleString()} chars
              </span>
            </div>
          </div>
        </div>

        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            className="inline-flex size-6 items-center justify-center rounded-sm text-text-muted hover:text-text focus-visible:outline-none"
            aria-label="Dismiss validation report"
          >
            <X className="size-4" />
          </button>
        )}
      </div>

      {!isValid && report.issues.length > 0 && (
        <div className="mt-3 grid gap-2 border-t border-border/80 pt-3">
          {errors.map((issue, idx) => (
            <div
              key={`err-${idx}`}
              className="flex items-start gap-2 rounded-sm border border-destructive/20 bg-surface p-2.5 text-xs text-text"
            >
              <span className="shrink-0 rounded-sm bg-destructive px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-destructive-foreground">
                Error
              </span>
              <div className="grid gap-0.5">
                <p className="font-semibold text-text">{issue.message}</p>
                <p className="text-[11px] text-text-muted font-mono">
                  Path: {issue.path || 'form'} · Code: {issue.code}
                </p>
              </div>
            </div>
          ))}

          {warnings.map((issue, idx) => (
            <div
              key={`warn-${idx}`}
              className="flex items-start gap-2 rounded-sm border border-warning/40 bg-surface p-2.5 text-xs text-text"
            >
              <span className="shrink-0 rounded-sm bg-warning px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-warning-foreground">
                Warning
              </span>
              <div className="grid gap-0.5">
                <p className="font-semibold text-text">{issue.message}</p>
                <p className="text-[11px] text-text-muted font-mono">
                  Path: {issue.path || 'form'} · Code: {issue.code}
                </p>
              </div>
            </div>
          ))}

          {infos.map((issue, idx) => (
            <div
              key={`info-${idx}`}
              className="flex items-start gap-2 rounded-sm border border-border bg-surface p-2.5 text-xs text-text"
            >
              <span className="shrink-0 rounded-sm bg-surface-subtle px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-text-muted border border-border">
                Info
              </span>
              <div className="grid gap-0.5">
                <p className="font-semibold text-text">{issue.message}</p>
                <p className="text-[11px] text-text-muted font-mono">
                  Path: {issue.path || 'form'} · Code: {issue.code}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
