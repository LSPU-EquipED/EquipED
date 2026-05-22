import { useMemo, useState } from 'react';
import { Outlet } from '@tanstack/react-router';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { adminApi } from '../api/admin.api';
import { usePromptVersions } from '../hooks/usePromptVersions';
import { PromptVersionHistory } from './PromptVersionHistory';

const agentId = 'coordinator';

export function AgentPromptEditor() {
  const queryClient = useQueryClient();
  const { data } = usePromptVersions(agentId);
  const [promptText, setPromptText] = useState('');
  const [motivation, setMotivation] = useState('');

  const latestPrompt = useMemo(() => data?.versions?.[0]?.prompt_text ?? '', [data]);

  const savePrompt = useMutation({
    mutationFn: () => adminApi.createPrompt(agentId, { prompt_text: promptText || latestPrompt, motivation }),
    onSuccess: async () => {
      setPromptText('');
      setMotivation('');
      await queryClient.invalidateQueries({ queryKey: ['promptVersions', agentId] });
    },
  });

  return (
    <section className="grid gap-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Admin</p>
        <h1 className="mt-2 text-2xl font-semibold">Prompt editor</h1>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.8fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Edit prompt</CardTitle>
            <CardDescription>Current agent: {agentId}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <textarea
              value={promptText}
              onChange={(event) => setPromptText(event.target.value)}
              rows={12}
              className="min-h-40 rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
              placeholder={latestPrompt || 'Enter prompt text...'}
            />
            <textarea
              value={motivation}
              onChange={(event) => setMotivation(event.target.value)}
              rows={3}
              className="min-h-24 rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
              placeholder="Motivation for this update"
            />
            <Button onClick={() => savePrompt.mutate()} disabled={savePrompt.isPending} className="w-fit">
              {savePrompt.isPending ? 'Saving...' : 'Save prompt'}
            </Button>
          </CardContent>
        </Card>

        <PromptVersionHistory agentId={agentId} />
      </div>

      <Outlet />
    </section>
  );
}
