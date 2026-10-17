import { Warning } from '@phosphor-icons/react';
import { Link } from '@tanstack/react-router';
import { TARGET_AGENT_META, isTargetAgent } from '@equiped/types';
import type { HistoryEvaluationItem } from '../types';
import { formatDate, formatDuration } from '../utils/historyFormatters';

interface HistoryRunDetailsProps {
  record: HistoryEvaluationItem;
  copiedId: string | null;
  onCopyId: (id: string) => void;
}

export function HistoryRunDetails({
  record,
  copiedId,
  onCopyId,
}: HistoryRunDetailsProps) {
  const duration = formatDuration(
    record.duration_seconds,
    record.submitted_at,
    record.completed_at,
  );
  return (
    <div role="region" aria-label="Run details" className="space-y-4 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="font-semibold text-text">Run details</span>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <Link
            to="/documents"
            className="font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-ring"
          >
            Module library
          </Link>
          {isTargetAgent(record.target_agent) && (
            <Link
              to="/specialists/$agentId/$documentId"
              params={{
                agentId: record.target_agent,
                documentId: record.document_id,
              }}
              className="font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-ring"
            >
              {TARGET_AGENT_META[record.target_agent].shortLabel} workspace
            </Link>
          )}
        </div>
      </div>
      <dl className="grid min-w-0 gap-x-6 gap-y-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="min-w-0">
          <dt className="text-text-muted">Specialist</dt>
          <dd className="m-0 mt-1 text-text">
            {isTargetAgent(record.target_agent)
              ? TARGET_AGENT_META[record.target_agent].fullName
              : record.target_agent === 'all'
                ? 'All domains'
                : (record.target_agent ?? '—')}
          </dd>
        </div>
        <div>
          <dt className="text-text-muted">Submitted</dt>
          <dd className="m-0 mt-1 text-text tabular-nums">
            <time dateTime={record.submitted_at}>
              {formatDate(record.submitted_at)}
            </time>
          </dd>
        </div>
        <div>
          <dt className="text-text-muted">Completed</dt>
          <dd className="m-0 mt-1 text-text tabular-nums">
            {record.completed_at ? (
              <time dateTime={record.completed_at}>
                {formatDate(record.completed_at)}
              </time>
            ) : (
              '—'
            )}
          </dd>
        </div>
        <div>
          <dt className="text-text-muted">Duration</dt>
          <dd className="m-0 mt-1 text-text tabular-nums">{duration ?? '—'}</dd>
        </div>
        {record.submitted_by && (
          <div className="min-w-0">
            <dt className="text-text-muted">Submitted by</dt>
            <dd className="m-0 mt-1 break-words text-text">
              {record.submitted_by}
            </dd>
          </div>
        )}
      </dl>
      <dl className="grid min-w-0 gap-x-6 gap-y-4 border-t border-border pt-4 sm:grid-cols-2">
        <div className="min-w-0">
          <dt className="text-text-muted">Evaluation ID</dt>
          <dd className="m-0 mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="break-all font-mono text-xs text-text-muted">
              {record.evaluation_id}
            </span>
            <button
              type="button"
              onClick={() => onCopyId(record.evaluation_id)}
              aria-label="Copy full evaluation ID"
              className="inline-flex min-h-8 items-center font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-ring"
            >
              {copiedId === record.evaluation_id ? 'Copied' : 'Copy ID'}
            </button>
          </dd>
        </div>
        <div className="min-w-0">
          <dt className="text-text-muted">Document ID</dt>
          <dd className="m-0 mt-1 break-all font-mono text-xs text-text-muted">
            {record.document_id}
          </dd>
        </div>
        {record.syllabus_id && (
          <div className="min-w-0">
            <dt className="text-text-muted">Syllabus reference</dt>
            <dd className="m-0 mt-1 break-all font-mono text-xs text-text-muted">
              {record.syllabus_id}
            </dd>
          </div>
        )}
        {record.curriculum_id && (
          <div className="min-w-0">
            <dt className="text-text-muted">Curriculum reference</dt>
            <dd className="m-0 mt-1 break-all font-mono text-xs text-text-muted">
              {record.curriculum_id}
            </dd>
          </div>
        )}
      </dl>

      {record.error_message && (
        <div className="flex items-center gap-2 rounded-xs border border-destructive/30 bg-destructive-soft p-2.5 text-xs text-destructive">
          <Warning className="size-4 shrink-0" aria-hidden="true" />
          <span>{record.error_message}</span>
        </div>
      )}
    </div>
  );
}
