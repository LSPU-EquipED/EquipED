import { Loader2, RotateCcw } from 'lucide-react';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { usePromptVersions } from '../hooks/usePromptVersions';
import type { PromptVersionItem } from '../types';

interface PromptVersionHistoryProps {
  agentId: string;
  onSelectVersion?: (version: PromptVersionItem) => void;
}

export function PromptVersionHistory({ agentId, onSelectVersion }: PromptVersionHistoryProps) {
  const { data, isLoading, isError } = usePromptVersions(agentId);

  return (
    <div className="rounded-md border border-border bg-surface overflow-hidden">
      <div className="border-b border-border p-6 bg-surface-subtle">
        <h2 className="text-sm font-bold uppercase tracking-wider text-text">
          Version History
        </h2>
        <p className="text-xs text-text-muted font-semibold mt-1 uppercase tracking-wider">
          Prompt revisions for {agentId}
        </p>
      </div>
      <div className="p-6 grid gap-3 max-h-[700px] overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center gap-2 text-xs font-semibold text-text-muted uppercase tracking-wider py-4">
            <Loader2 className="size-4 animate-spin" /> Loading versions...
          </div>
        ) : isError ? (
          <p className="text-xs font-semibold text-destructive uppercase tracking-wider py-4">
            Failed to load versions.
          </p>
        ) : !data?.versions.length ? (
          <p className="text-xs font-semibold text-text-muted uppercase tracking-wider py-4">
            No versions yet.
          </p>
        ) : (
          data.versions.map((version) => (
            <div
              key={version.version_id}
              className="rounded-sm border border-border p-4 text-xs bg-surface-subtle/40 space-y-2"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <strong className="font-bold text-text tabular-nums">v{version.version_number}</strong>
                  <Badge variant={version.is_active ? 'success' : 'neutral'} withDot>
                    {version.is_active ? 'Active' : 'Archived'}
                  </Badge>
                </div>
                {onSelectVersion ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => onSelectVersion(version)}
                    className="h-7 px-2 text-xs font-semibold text-primary hover:text-primary-strong"
                    title="Load this prompt into editor"
                  >
                    <RotateCcw className="size-3 mr-1" />
                    Load
                  </Button>
                ) : null}
              </div>
              <p className="whitespace-pre-wrap text-text font-medium leading-relaxed max-h-36 overflow-y-auto font-mono text-[11px] bg-surface p-2 rounded-xs border border-border">
                {version.prompt_text}
              </p>
              {version.motivation ? (
                <p className="text-xs text-text-muted italic">
                  Motivation: {version.motivation}
                </p>
              ) : null}
              <p className="text-[10px] font-semibold text-text-muted uppercase tracking-wider tabular-nums pt-1 border-t border-border/50">
                {version.updated_by || 'System'} · {new Date(version.created_at).toLocaleString()}
              </p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
