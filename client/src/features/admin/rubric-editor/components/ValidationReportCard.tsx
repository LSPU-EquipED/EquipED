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
          ? 'border-[#3b963e]/40 bg-[#3b963e]/5 text-slate-800'
          : 'border-[#b91c1c]/40 bg-[#b91c1c]/5 text-slate-800'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          {isValid ? (
            <CheckCircle2 className="size-5 shrink-0 text-[#3b963e] mt-0.5" aria-hidden="true" />
          ) : (
            <AlertCircle className="size-5 shrink-0 text-[#b91c1c] mt-0.5" aria-hidden="true" />
          )}
          <div>
            <h3 className="text-sm font-bold tracking-tight">
              {isValid
                ? 'Form Conforms to Agent Capability Manifest'
                : `Validation Issues Detected (${report.issues.length})`}
            </h3>
            <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-slate-600 font-semibold uppercase tracking-wider">
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
            className="inline-flex size-6 items-center justify-center rounded-sm text-slate-400 hover:text-slate-600 focus:outline-none"
            aria-label="Dismiss validation report"
          >
            <X className="size-4" />
          </button>
        )}
      </div>

      {!isValid && report.issues.length > 0 && (
        <div className="mt-3 grid gap-2 border-t border-slate-200/80 pt-3">
          {errors.map((issue, idx) => (
            <div
              key={`err-${idx}`}
              className="flex items-start gap-2 rounded-sm border border-[#b91c1c]/20 bg-white p-2.5 text-xs text-slate-700"
            >
              <span className="shrink-0 rounded-sm bg-[#b91c1c] px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">
                Error
              </span>
              <div className="grid gap-0.5">
                <p className="font-semibold text-slate-800">{issue.message}</p>
                <p className="text-[11px] text-slate-500 font-mono">
                  Path: {issue.path || 'form'} · Code: {issue.code}
                </p>
              </div>
            </div>
          ))}

          {warnings.map((issue, idx) => (
            <div
              key={`warn-${idx}`}
              className="flex items-start gap-2 rounded-sm border border-[#f2c811]/40 bg-white p-2.5 text-xs text-slate-700"
            >
              <span className="shrink-0 rounded-sm bg-[#f2c811] px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-900">
                Warning
              </span>
              <div className="grid gap-0.5">
                <p className="font-semibold text-slate-800">{issue.message}</p>
                <p className="text-[11px] text-slate-500 font-mono">
                  Path: {issue.path || 'form'} · Code: {issue.code}
                </p>
              </div>
            </div>
          ))}

          {infos.map((issue, idx) => (
            <div
              key={`info-${idx}`}
              className="flex items-start gap-2 rounded-sm border border-slate-200 bg-white p-2.5 text-xs text-slate-700"
            >
              <span className="shrink-0 rounded-sm bg-slate-500 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">
                Info
              </span>
              <div className="grid gap-0.5">
                <p className="font-semibold text-slate-800">{issue.message}</p>
                <p className="text-[11px] text-slate-500 font-mono">
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
