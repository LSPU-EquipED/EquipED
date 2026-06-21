import { useMemo, useState } from 'react';
import { useNavigate, useParams } from '@tanstack/react-router';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '../api/admin.api';
import { usePromptVersions } from '../hooks/usePromptVersions';
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
      adminApi.createPrompt(activeAgent, { prompt_text: promptText.trim(), motivation }),
    onSuccess: async () => {
      setPromptText('');
      setMotivation('');
      await queryClient.invalidateQueries({ queryKey: ['promptVersions', activeAgent] });
    },
  });

  return (
    <section key={activeAgent} className="grid gap-6">

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.8fr)]">
        <div className="border border-slate-200 bg-white rounded-sm">
          <div className="border-b border-slate-200 p-6 bg-slate-50/50">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800">Edit Prompt</h2>
            <div className="flex items-center gap-3 mt-3 text-xs font-bold text-slate-500 uppercase tracking-wider">
              <span>Current Agent:</span>
              <select
                value={activeAgent}
                onChange={(e) => {
                  void navigate({ to: '/admin/prompts/$agentId', params: { agentId: e.target.value } });
                }}
                className="w-56 h-8 border border-slate-200 bg-white px-2 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] rounded-sm text-xs font-bold text-slate-700 cursor-pointer"
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
              className="min-h-40 rounded-sm border border-slate-200 bg-white px-3 py-2 text-sm outline-none placeholder:text-slate-400 font-medium text-slate-800 focus:ring-2 focus:ring-[#1b3b87]"
              placeholder={latestPrompt || 'Enter prompt text...'}
            />
            <textarea
              value={motivation}
              onChange={(event) => setMotivation(event.target.value)}
              rows={3}
              className="min-h-24 rounded-sm border border-slate-200 bg-white px-3 py-2 text-sm outline-none placeholder:text-slate-400 font-medium text-slate-800 focus:ring-2 focus:ring-[#1b3b87]"
              placeholder="Motivation for this update"
            />
            <button
              type="button"
              onClick={() => savePrompt.mutate()}
              disabled={savePrompt.isPending || !promptText.trim()}
              className="w-fit h-10 inline-flex items-center justify-center bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-white px-4 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87] focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {savePrompt.isPending ? 'Saving...' : 'Save Prompt'}
            </button>
            {savePrompt.isError && (
              <p className="text-sm font-semibold text-red-750">
                {savePrompt.error instanceof Error
                  ? savePrompt.error.message
                  : 'Failed to save prompt'}
              </p>
            )}
          </div>
        </div>

        <PromptVersionHistory agentId={activeAgent} />
      </div>
    </section>
  );
}
