import { getErrorMessage } from '@equiped/api-client';
import { useState, type FormEvent } from 'react';
import { useCreatePrompt, usePromptVersions, useRevertPrompt } from './usePromptVersions';
import type { PromptVersionItem } from '../types';

export function usePromptEditor(agentId: string) {
  const history = usePromptVersions(agentId);
  const createPrompt = useCreatePrompt(agentId);
  const revertPrompt = useRevertPrompt(agentId);
  const activeVersion = history.data?.versions.find((version) => version.is_active) ?? null;
  const [draft, setDraft] = useState<string | null>(null);
  const [motivation, setMotivation] = useState('');
  const [copyStatus, setCopyStatus] = useState<'idle' | 'copied' | 'failed'>('idle');
  const [restoreVersion, setRestoreVersion] = useState<PromptVersionItem | null>(null);
  const [restoreOpen, setRestoreOpen] = useState(false);

  const activeText = activeVersion?.prompt_text ?? '';
  const promptText = draft ?? activeText;
  const hasChanges = promptText !== activeText || motivation.length > 0;
  const isPending = createPrompt.isPending || revertPrompt.isPending;
  const canSave =
    !history.isLoading &&
    !history.isError &&
    !isPending &&
    promptText.trim().length > 0 &&
    promptText.trim() !== activeText.trim();

  function updateDraft(value: string) {
    setDraft(value);
    setCopyStatus('idle');
  }

  function discard() {
    setDraft(null);
    setMotivation('');
    setCopyStatus('idle');
    createPrompt.reset();
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(promptText);
      setCopyStatus('copied');
    } catch {
      setCopyStatus('failed');
    }
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!canSave) return;
    try {
      await createPrompt.mutateAsync({
        prompt_text: promptText.trim(),
        motivation: motivation.trim() || undefined,
      });
      discard();
    } catch {
      // The mutation error is rendered beside the editor; keep the draft intact.
    }
  }

  function loadVersionDraft(version: PromptVersionItem) {
    updateDraft(version.prompt_text);
    setMotivation(`Derived from v${version.version_number}`);
    createPrompt.reset();
  }

  function requestRestore(version: PromptVersionItem) {
    revertPrompt.reset();
    setRestoreVersion(version);
    setRestoreOpen(true);
  }

  async function confirmRestore() {
    if (!restoreVersion || isPending) return;
    await revertPrompt.mutateAsync(restoreVersion.version_id);
    discard();
    setRestoreOpen(false);
  }

  return {
    history,
    activeVersion,
    promptText,
    motivation,
    setMotivation,
    copyStatus,
    hasChanges,
    isPending,
    canSave,
    isSaving: createPrompt.isPending,
    isRestoring: revertPrompt.isPending,
    saveError: createPrompt.isError
      ? getErrorMessage(createPrompt.error, 'Failed to save prompt revision.')
      : null,
    restoreError: revertPrompt.isError
      ? getErrorMessage(revertPrompt.error, 'Unable to restore this version. Try again.')
      : null,
    restoreVersion,
    restoreOpen,
    setRestoreOpen,
    updateDraft,
    discard,
    copy,
    save,
    loadVersionDraft,
    requestRestore,
    confirmRestore,
  };
}

export type PromptEditorState = ReturnType<typeof usePromptEditor>;
