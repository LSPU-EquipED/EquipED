import { Loader2 } from 'lucide-react';
import { usePromptVersions } from '../hooks/usePromptVersions';

interface PromptVersionHistoryProps {
  agentId: string;
}

export function PromptVersionHistory({ agentId }: PromptVersionHistoryProps) {
  const { data, isLoading, isError } = usePromptVersions(agentId);

  return (
    <div className="border border-slate-200 bg-white rounded-sm">
      <div className="border-b border-slate-200 p-6 bg-slate-50/50">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800">Version History</h2>
        <p className="text-xs text-slate-500 font-semibold mt-1 uppercase tracking-wider">Prompt revisions for {agentId}</p>
      </div>
      <div className="p-6 grid gap-3">
        {isLoading ? (
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
            <Loader2 className="size-4 animate-spin" /> Loading versions...
          </div>
        ) : isError ? (
          <p className="text-xs font-semibold text-red-700 uppercase tracking-wider">Failed to load versions.</p>
        ) : !data?.versions.length ? (
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">No versions yet.</p>
        ) : (
          data.versions.map((version) => (
            <div key={version.version_id} className="rounded-sm border border-slate-200 p-3 text-xs bg-slate-50/10">
              <div className="flex items-center justify-between gap-3">
                <strong className="font-bold text-slate-800">v{version.version_number}</strong>
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  {version.is_active ? 'Active' : 'Archived'}
                </span>
              </div>
              <p className="mt-2 whitespace-pre-wrap text-slate-700 font-medium">
                {version.prompt_text}
              </p>
              <p className="mt-2 text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                {version.updated_by || 'System'} · {new Date(version.created_at).toLocaleString()}
              </p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
