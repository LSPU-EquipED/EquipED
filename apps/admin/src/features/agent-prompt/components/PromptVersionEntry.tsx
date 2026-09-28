import { CaretDown } from '@phosphor-icons/react';
import { Badge, Button, cn } from '@equiped/ui';
import type { PromptVersionItem } from '../types';

type PromptVersionEntryProps = {
  version: PromptVersionItem;
  disabled?: boolean;
  onSelectVersion: (version: PromptVersionItem) => void;
  onRevertVersion: (version: PromptVersionItem) => void;
};

export function PromptVersionEntry({
  version,
  disabled,
  onSelectVersion,
  onRevertVersion,
}: PromptVersionEntryProps) {
  return (
    <li className={cn('space-y-3 p-5', version.is_active && 'bg-primary-soft/30')}>
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold tabular-nums text-text">
          Version {version.version_number}
        </h3>
        {version.is_active ? (
          <Badge variant="success" withDot>
            Active
          </Badge>
        ) : null}
      </div>
      {version.motivation ? (
        <p className="break-words text-sm leading-relaxed text-text">{version.motivation}</p>
      ) : null}
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-xs text-text-muted">
        <span className="min-w-0 break-all" title={version.updated_by ?? 'System'}>
          By {version.updated_by || 'System'}
        </span>
        <time dateTime={version.created_at} className="tabular-nums">
          {new Date(version.created_at).toLocaleString(undefined, {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          })}
        </time>
      </div>
      <details className="group">
        <summary className="cursor-pointer list-none rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <p className="line-clamp-3 whitespace-pre-wrap break-words font-mono text-[13px] leading-relaxed text-text-muted group-open:hidden">
            {version.prompt_text}
          </p>
          <span className="mt-2 inline-flex min-h-10 items-center gap-2 text-xs font-semibold text-primary">
            <span className="group-open:hidden">View full prompt</span>
            <span className="hidden group-open:inline">Hide prompt</span>
            <CaretDown
              className="size-3.5 transition-transform duration-120 group-open:rotate-180 motion-reduce:transition-none"
              aria-hidden="true"
            />
          </span>
        </summary>
        <p className="mt-2 whitespace-pre-wrap break-words font-mono text-[13px] leading-relaxed text-text">
          {version.prompt_text}
        </p>
      </details>
      {!version.is_active ? (
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="min-h-10"
            disabled={disabled}
            onClick={() => onSelectVersion(version)}
            aria-label={`Use version ${version.version_number} as draft`}
          >
            Use as draft
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="min-h-10"
            disabled={disabled}
            onClick={() => onRevertVersion(version)}
            aria-label={`Restore version ${version.version_number}`}
          >
            Restore version
          </Button>
        </div>
      ) : null}
    </li>
  );
}
