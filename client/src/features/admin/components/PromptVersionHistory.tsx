import { Loader2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { usePromptVersions } from '../hooks/usePromptVersions';

interface PromptVersionHistoryProps {
  agentId: string;
}

export function PromptVersionHistory({ agentId }: PromptVersionHistoryProps) {
  const { data, isLoading, isError } = usePromptVersions(agentId);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Version history</CardTitle>
        <CardDescription>Prompt revisions for {agentId}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {isLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" /> Loading versions...</div>
        ) : isError ? (
          <p className="text-sm text-destructive">Failed to load versions.</p>
        ) : !data?.versions.length ? (
          <p className="text-sm text-muted-foreground">No versions yet.</p>
        ) : (
          data.versions.map((version) => (
            <div key={version.version_id} className="rounded-lg border p-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <strong>v{version.version_number}</strong>
                <span className="text-xs text-muted-foreground">{version.is_active ? 'Active' : 'Archived'}</span>
              </div>
              <p className="mt-2 whitespace-pre-wrap text-muted-foreground">{version.prompt_text}</p>
              <p className="mt-2 text-xs text-muted-foreground">
                {version.updated_by || 'System'} · {new Date(version.created_at).toLocaleString()}
              </p>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
