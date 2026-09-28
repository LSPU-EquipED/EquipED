import { Check, Copy, FloppyDisk } from '@phosphor-icons/react';
import { Button, Skeleton } from '@equiped/ui';
import type { PromptEditorState } from '../hooks/usePromptEditor';

type PromptEditorPanelProps = {
  agentLabel: string;
  editor: Pick<
    PromptEditorState,
    | 'history'
    | 'activeVersion'
    | 'promptText'
    | 'motivation'
    | 'hasChanges'
    | 'isPending'
    | 'canSave'
    | 'save'
    | 'copy'
    | 'copyStatus'
    | 'updateDraft'
    | 'setMotivation'
    | 'isSaving'
    | 'saveError'
    | 'discard'
  >;
};

export function PromptEditorPanel({ agentLabel, editor }: PromptEditorPanelProps) {
  const { history, activeVersion, promptText, motivation, hasChanges, isPending, canSave } = editor;
  return (
    <section
      aria-labelledby="prompt-editor-heading"
      className="min-w-0 overflow-hidden rounded-md border border-border bg-surface lg:col-span-7"
    >
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-5 py-4">
        <div>
          <h2 id="prompt-editor-heading" className="text-base font-semibold text-text">
            System prompt
          </h2>
          <p className="mt-1 text-sm text-text-muted">{agentLabel}</p>
        </div>
        <span className="text-xs font-medium text-text-muted" role="status">
          {hasChanges
            ? 'Unsaved changes'
            : activeVersion
              ? `Editing from v${activeVersion.version_number}`
              : 'New prompt'}
        </span>
      </header>

      {history.isLoading ? (
        <div role="status" aria-label="Loading system prompt" className="space-y-5 p-5">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-80 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-40" />
        </div>
      ) : history.isError ? (
        <div role="alert" className="space-y-3 p-5 text-sm">
          <p className="text-destructive">Unable to load this agent’s prompt.</p>
          <Button type="button" variant="secondary" onClick={() => void history.refetch()}>
            Try again
          </Button>
        </div>
      ) : (
        <form onSubmit={editor.save} className="space-y-5 p-5">
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-3">
              <label htmlFor="prompt-text" className="text-xs font-semibold text-text">
                Prompt text <span className="text-destructive">*</span>
              </label>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="min-h-10 gap-2"
                onClick={() => void editor.copy()}
                disabled={!promptText}
              >
                {editor.copyStatus === 'copied' ? (
                  <Check className="size-4" aria-hidden="true" />
                ) : (
                  <Copy className="size-4" aria-hidden="true" />
                )}
                {editor.copyStatus === 'copied' ? 'Copied' : 'Copy prompt'}
              </Button>
            </div>
            <textarea
              id="prompt-text"
              value={promptText}
              onChange={(event) => editor.updateDraft(event.target.value)}
              rows={16}
              maxLength={10000}
              disabled={isPending}
              className="block w-full resize-y rounded-sm border border-input bg-surface p-4 font-mono text-[13px] leading-relaxed text-text placeholder:text-text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
              placeholder="Enter system instructions for this agent…"
              aria-describedby="prompt-save-help"
              required
            />
            <div className="flex flex-wrap items-start justify-between gap-2 text-xs text-text-muted">
              <p id="prompt-save-help" className="max-w-sm">
                Saving publishes a new active version for future evaluations.
              </p>
              <span className="shrink-0 tabular-nums">
                {promptText.length.toLocaleString()} characters ·{' '}
                {promptText ? promptText.split('\n').length : 0} lines
              </span>
            </div>
            {editor.copyStatus === 'failed' ? (
              <p role="alert" className="text-xs text-destructive">
                Could not copy the prompt. Select the text and copy it manually.
              </p>
            ) : null}
          </div>

          <div className="space-y-2">
            <label htmlFor="prompt-motivation" className="text-xs font-semibold text-text">
              Change note <span className="font-normal text-text-muted">(optional)</span>
            </label>
            <input
              id="prompt-motivation"
              type="text"
              value={motivation}
              onChange={(event) => editor.setMotivation(event.target.value)}
              disabled={isPending}
              placeholder="Describe what changed and why"
              className="h-10 w-full rounded-sm border border-input bg-surface px-3 text-sm text-text placeholder:text-text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
            />
          </div>

          {editor.saveError ? (
            <p
              role="alert"
              className="rounded-sm border border-destructive/30 bg-destructive-soft p-3 text-sm text-destructive"
            >
              {editor.saveError}
            </p>
          ) : null}

          <div className="flex flex-wrap items-center gap-3 border-t border-border pt-4">
            <Button
              type="submit"
              variant="primary"
              disabled={!canSave}
              isLoading={editor.isSaving}
              className="gap-2"
            >
              <FloppyDisk className="size-4" aria-hidden="true" />
              {editor.isSaving ? 'Saving version…' : 'Save new revision'}
            </Button>
            {hasChanges ? (
              <Button
                type="button"
                variant="secondary"
                disabled={isPending}
                onClick={editor.discard}
              >
                Discard changes
              </Button>
            ) : null}
          </div>
        </form>
      )}
    </section>
  );
}
