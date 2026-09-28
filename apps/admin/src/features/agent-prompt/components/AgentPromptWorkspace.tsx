import { usePromptEditor } from '../hooks/usePromptEditor';
import { PromptVersionHistory } from './PromptVersionHistory';
import { RevertPromptModal } from './RevertPromptModal';
import { PromptEditorPanel } from './PromptEditorPanel';

export function AgentPromptWorkspace({
  agentId,
  agentLabel,
}: {
  agentId: string;
  agentLabel: string;
}) {
  const editor = usePromptEditor(agentId);
  const { history, isPending } = editor;

  return (
    <div
      id={`prompt-panel-${agentId}`}
      role="tabpanel"
      aria-labelledby={`prompt-tab-${agentId}`}
      tabIndex={0}
    >
      <div className="grid items-start gap-6 lg:grid-cols-12">
        <PromptEditorPanel agentLabel={agentLabel} editor={editor} />

        <div className="min-w-0 lg:col-span-5">
          <PromptVersionHistory
            history={history}
            disabled={isPending}
            onSelectVersion={editor.loadVersionDraft}
            onRevertVersion={editor.requestRestore}
          />
        </div>
      </div>
      <RevertPromptModal
        isOpen={editor.restoreOpen}
        onClose={() => editor.setRestoreOpen(false)}
        onConfirm={editor.confirmRestore}
        agentLabel={agentLabel}
        versionNumber={editor.restoreVersion?.version_number ?? 0}
        isPending={editor.isRestoring}
        error={editor.restoreError}
      />
    </div>
  );
}
