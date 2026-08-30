import { useMemo, useState } from 'react';
import { useNavigate, useParams } from '@tanstack/react-router';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/shared/components/Button';
import { agentPromptApi } from '../api/agentPrompt.api';
import { usePromptVersions } from '../hooks/usePromptVersions';
import type { PromptVersionItem } from '../types';
import { PromptVersionHistory } from './PromptVersionHistory';

const AGENTS = [
  { id: 'coordinator', label: 'Program Coordinator' },
  { id: 'sme', label: 'Subject Matter Expert' },
  { id: 'gad', label: 'GAD' },
  { id: 'itso', label: 'ITSO' },
] as const;

export function AgentPromptEditor() {
  const { agentId } = useParams({ strict: false }) as { agentId?: string };
  const navigate = useNavigate();
  const activeAgent = agentId ?? 'coordinator';

  const queryClient = useQueryClient();
  const { data } = usePromptVersions(activeAgent);
  const [promptText, setPromptText] = useState('');
  const [motivation, setMotivation] = useState('');

  const latestPrompt = useMemo(() => data?.versions?.[0]?.prompt_text ?? '', [data]);

  const savePrompt = useMutation({
    mutationFn: () =>
      agentPromptApi.createPrompt(activeAgent, { prompt_text: promptText.trim(), motivation }),
    onSuccess: async () => {
      setPromptText('');
      setMotivation('');
      await queryClient.invalidateQueries({ queryKey: ['promptVersions', activeAgent] });
    },
  });

  const handleSelectVersion = (version: PromptVersionItem) => {
    setPromptText(version.prompt_text);
    setMotivation(`Reverted to v${version.version_number}`);
  };

  return (
    <section key={activeAgent} className="grid gap-6">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.8fr)]">
        <div className="rounded-md border border-border bg-surface overflow-hidden">
          <div className="border-b border-border p-6 bg-surface-subtle">
            <h2 className="text-sm font-bold uppercase tracking-wider text-text">
              Edit Prompt
            </h2>
            <div className="flex items-center gap-3 mt-3 text-xs font-semibold text-text-muted uppercase tracking-wider">
              <span>Current Agent:</span>
              <select
                value={activeAgent}
                onChange={(e) => {
                  void navigate({
                    to: '/admin/prompts/$agentId',
                    params: { agentId: e.target.value },
                  });
                }}
                className="w-56 h-8 border border-input bg-surface px-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm text-xs font-semibold text-text cursor-pointer"
              >
                {AGENTS.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="p-6 grid gap-4">
            <textarea
              value={promptText}
              onChange={(event) => setPromptText(event.target.value)}
              rows={12}
              className="min-h-40 rounded-sm border border-input bg-surface px-3 py-2 text-sm outline-none placeholder:text-text-muted font-medium text-text focus-visible:ring-2 focus-visible:ring-ring"
              placeholder={latestPrompt || 'Enter prompt text...'}
            />
            <textarea
              value={motivation}
              onChange={(event) => setMotivation(event.target.value)}
              rows={3}
              className="min-h-24 rounded-sm border border-input bg-surface px-3 py-2 text-sm outline-none placeholder:text-text-muted font-medium text-text focus-visible:ring-2 focus-visible:ring-ring"
              placeholder="Motivation for this update"
            />
            <Button
              type="button"
              variant="primary"
              onClick={() => savePrompt.mutate()}
              disabled={savePrompt.isPending || !promptText.trim()}
              isLoading={savePrompt.isPending}
              className="w-fit text-xs font-semibold uppercase tracking-wider"
            >
              Save Prompt
            </Button>
            {savePrompt.isError && (
              <p className="text-sm font-semibold text-destructive">
                {savePrompt.error instanceof Error
                  ? savePrompt.error.message
                  : 'Failed to save prompt'}
              </p>
            )}
          </div>
        </div>

        <PromptVersionHistory agentId={activeAgent} onSelectVersion={handleSelectVersion} />
      </div>
    </section>
  );
}
