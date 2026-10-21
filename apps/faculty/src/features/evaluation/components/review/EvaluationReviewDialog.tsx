import { useState } from "react";
import { useBlocker } from "@tanstack/react-router";
import { ConfirmationModal } from "@equiped/ui";
import { AgentReviewModal } from "./AgentReviewModal";
import type { CriterionScoreItem } from "../../types";

interface EvaluationReviewDialogProps {
  agentName: string;
  evaluationId: string;
  criteria: readonly CriterionScoreItem[];
  onClose: () => void;
}
/** Preserve unsaved review drafts across both result entry points. */
export function EvaluationReviewDialog(props: EvaluationReviewDialogProps) {
  const [dirty, setDirty] = useState(false);
  const blocker = useBlocker({
    shouldBlockFn: () => dirty,
    enableBeforeUnload: dirty,
    withResolver: true,
  });
  return (
    <>
      <AgentReviewModal {...props} onDirtyChange={setDirty} />
      <ConfirmationModal
        isOpen={blocker.status === "blocked"}
        title="Leave this review?"
        description="You have unsaved score edits. Keep editing or discard them to continue."
        variant="warning"
        confirmLabel="Discard and leave"
        cancelLabel="Keep editing"
        onClose={() => blocker.reset?.()}
        onConfirm={() => blocker.proceed?.()}
      />
    </>
  );
}
