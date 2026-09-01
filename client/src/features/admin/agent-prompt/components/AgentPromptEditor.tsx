import { useMemo, useState } from 'react';
import { useNavigate, useParams } from '@tanstack/react-router';
import {
  Check,
  Copy,
  FloppyDisk,
  Gear,
  X,
} from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/components/utils';
import { useCreatePrompt, usePromptVersions, useRevertPrompt } from '../hooks/usePromptVersions';
import type { PromptVersionItem } from '../types';
import { PromptVersionHistory } from './PromptVersionHistory';
import { RevertPromptModal } from './RevertPromptModal';

const AGENTS = [
  { id: 'coordinator', label: 'Program Coordinator' },
  { id: 'sme', label: 'Subject Matter Expert' },
  { id: 'gad', label: 'Gender & Development (GAD)' },
  { id: 'itso', label: 'Intellectual Property (ITSO)' },
] as const;

export function AgentPromptEditor() {
  const { agentId } = useParams({ strict: false }) as { agentId?: string };
  const navigate = useNavigate();
  const activeAgent = agentId ?? 'coordinator';
  const activeAgentMeta = AGENTS.find((a) => a.id === activeAgent) ?? AGENTS[0];

  const { data } = usePromptVersions(activeAgent);
  const createPrompt = useCreatePrompt(activeAgent);
  const revertPrompt = useRevertPrompt(activeAgent);

  const [promptText, setPromptText] = useState('');
  const [motivation, setMotivation] = useState('');
  const [copied, setCopied] = useState(false);
  const [revertModal, setRevertModal] = useState<{
    isOpen: boolean;
    version: PromptVersionItem | null;
  }>({ isOpen: false, version: null });

  const activeVersion = useMemo(
    () => data?.versions?.find((v) => v.is_active) ?? data?.versions?.[0] ?? null,
    [data],
  );

  const latestPrompt = activeVersion?.prompt_text ?? '';

  // Calculate live editor metrics
  const activeContent = promptText.trim() || latestPrompt;
  const characterCount = activeContent.length;
  const lineCount = activeContent ? activeContent.split('\n').length : 0;

  const handleCopy = () => {
    const textToCopy = promptText || latestPrompt;
    if (!textToCopy) return;
    void navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!promptText.trim()) return;

    try {
      await createPrompt.mutateAsync({
        prompt_text: promptText.trim(),
        motivation: motivation.trim() || undefined,
      });
      setPromptText('');
      setMotivation('');
    } catch {
      // Handled by mutation error
    }
  };

  const handleSelectVersion = (version: PromptVersionItem) => {
    setPromptText(version.prompt_text);
    setMotivation(`Derived from v${version.version_number}`);
  };

  const handleConfirmRevert = async (versionId: string) => {
    try {
      await revertPrompt.mutateAsync(versionId);
      setRevertModal({ isOpen: false, version: null });
    } catch {
      // Handled by mutation error
    }
  };

  return (
    <section key={activeAgent} className="space-y-6">
      {/* ── Top Navigation: Agent Tabs Container ───────────────────────── */}
      <div className="rounded-md border border-border bg-surface shadow-none overflow-hidden">
        <nav
          className="flex flex-wrap gap-1 px-4 pt-2 border-b border-border bg-surface-subtle"
          aria-label="Specialist Agents"
        >
          {AGENTS.map((agent) => {
            const isTabSelected = activeAgent === agent.id;
            return (
              <button
                key={agent.id}
                type="button"
                role="tab"
                aria-selected={isTabSelected}
                onClick={() => {
                  setPromptText('');
                  setMotivation('');
                  void navigate({
                    to: '/admin/prompts/$agentId',
                    params: { agentId: agent.id },
                  });
                }}
                className={cn(
                  'flex items-center gap-2 px-4 py-3 text-xs font-semibold transition-colors border-b-2 cursor-pointer select-none',
                  isTabSelected
                    ? 'border-primary text-primary font-bold bg-surface'
                    : 'border-transparent text-text-muted hover:text-text hover:border-border',
                )}
              >
                <Gear className="size-4" />
                <span>{agent.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* ── Main Two-Column Split Layout ───────────────────────────────── */}
      <div className="grid gap-6 lg:grid-cols-12 items-start">
        {/* Left Column (7 cols): System Directive Editor */}
        <div className="lg:col-span-7 rounded-md border border-border bg-surface overflow-hidden shadow-none">
          <div className="border-b border-border p-4 sm:p-5 bg-surface-subtle flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xs font-bold uppercase tracking-wider text-text">
                  System Directive Editor
                </h2>
                {activeVersion ? (
                  <Badge variant="success" withDot>
                    v{activeVersion.version_number} Active
                  </Badge>
                ) : null}
              </div>
              <p className="text-[11px] text-text-muted mt-0.5 font-medium">
                System instructions for {activeAgentMeta.label}
              </p>
            </div>

            {/* Live Metrics Pill */}
            <div className="flex items-center gap-2 text-xs font-mono tabular-nums text-text-muted rounded-xs bg-surface border border-border px-2.5 py-1">
              <span>{characterCount.toLocaleString()} chars</span>
              <span className="text-border">·</span>
              <span>{lineCount} lines</span>
            </div>
          </div>

          <form onSubmit={handleSave} className="p-5 sm:p-6 space-y-5">
            {/* Directive Textarea Header & Actions */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label htmlFor="prompt-text" className="text-xs font-semibold text-text">
                  Prompt Text <span className="text-destructive">*</span>
                </label>
                <button
                  type="button"
                  onClick={handleCopy}
                  className="inline-flex items-center gap-1 text-[11px] font-semibold text-primary hover:underline cursor-pointer"
                >
                  {copied ? (
                    <>
                      <Check className="size-3 text-success" />
                      <span className="text-success">Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="size-3" />
                      <span>Copy Directive</span>
                    </>
                  )}
                </button>
              </div>

              <textarea
                id="prompt-text"
                value={promptText}
                onChange={(event) => setPromptText(event.target.value)}
                rows={14}
                className="w-full rounded-sm border border-input bg-surface p-3 font-mono text-xs leading-relaxed text-text placeholder:text-text-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder={latestPrompt || 'Enter system prompt directives for this agent…'}
                required
              />
              <p className="text-[11px] text-text-muted">
                {promptText
                  ? 'Editing new prompt content. Click Save below to publish a new version.'
                  : 'Displaying active system prompt above. Type in the box to create a new revision.'}
              </p>
            </div>

            {/* Motivation Note Input */}
            <div className="space-y-1.5">
              <label htmlFor="prompt-motivation" className="text-xs font-semibold text-text">
                Update Motivation / Changelog Note
              </label>
              <input
                id="prompt-motivation"
                type="text"
                value={motivation}
                onChange={(event) => setMotivation(event.target.value)}
                placeholder="e.g. Hardened topic alignment rules and citation checks"
                className="h-10 w-full rounded-sm border border-input bg-surface px-3 text-xs font-semibold text-text placeholder:text-text-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              <p className="text-[11px] text-text-muted">
                Recorded in immutable audit logs for accreditation review.
              </p>
            </div>

            {/* Error Message */}
            {createPrompt.isError ? (
              <p
                role="alert"
                className="rounded-sm border border-destructive/30 bg-destructive-soft p-3 text-xs font-semibold text-destructive"
              >
                {createPrompt.error instanceof Error
                  ? createPrompt.error.message
                  : 'Failed to save prompt revision.'}
              </p>
            ) : null}

            {/* Action Buttons */}
            <div className="pt-2 flex items-center justify-between gap-4 border-t border-border">
              <Button
                type="submit"
                variant="primary"
                size="md"
                disabled={createPrompt.isPending || !promptText.trim()}
                isLoading={createPrompt.isPending}
                className="h-10 px-5 text-xs sm:text-sm font-semibold gap-1.5"
              >
                <FloppyDisk className="size-4" />
                <span>{createPrompt.isPending ? 'Saving version…' : 'Save New Revision'}</span>
              </Button>

              {promptText ? (
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setPromptText('');
                    setMotivation('');
                  }}
                  className="text-xs h-8 px-3 gap-1"
                >
                  <X className="size-3.5" />
                  <span>Discard Edits</span>
                </Button>
              ) : null}
            </div>
          </form>
        </div>

        {/* Right Column (5 cols): Revision History & Rollback Ledger */}
        <div className="lg:col-span-5">
          <PromptVersionHistory
            agentId={activeAgent}
            agentLabel={activeAgentMeta.label}
            onSelectVersion={handleSelectVersion}
            onRevertVersion={(version) => setRevertModal({ isOpen: true, version })}
          />
        </div>
      </div>

      {/* ── Revert Confirmation Modal ──────────────────────────────────── */}
      {revertModal.isOpen && revertModal.version && (
        <RevertPromptModal
          isOpen={revertModal.isOpen}
          onClose={() => setRevertModal({ isOpen: false, version: null })}
          onConfirm={() => handleConfirmRevert(revertModal.version!.version_id)}
          agentLabel={activeAgentMeta.label}
          versionNumber={revertModal.version.version_number}
          isPending={revertPrompt.isPending}
        />
      )}
    </section>
  );
}
