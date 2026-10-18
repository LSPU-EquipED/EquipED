import { useState } from "react";
import { ConfirmationModal } from "@equiped/ui";
import type { ClientDocument, TargetAgent } from "@equiped/types";
import type { DeskQueueItem } from "../types";
import { ModuleSetupView } from "./workspace/ModuleSetupView";
import { EvaluationSetupFields } from "./EvaluationSetupFields";
import { useEvaluationSetup } from "../hooks/useEvaluationSetup";

export interface SpecialistLaunchpadProps {
  activeItem: DeskQueueItem;
  activeDocument: ClientDocument | null;
  validAgent: TargetAgent;
  onSubmitted: (evaluationId: string) => void;
  onSelect: () => void;
}
export function SpecialistLaunchpad({
  activeItem,
  activeDocument,
  validAgent,
  onSubmitted,
  onSelect,
}: SpecialistLaunchpadProps) {
  const [confirm, setConfirm] = useState(false);
  const setup = useEvaluationSetup({
    documentId: activeItem.document_id,
    detectedProgram: activeDocument?.program || activeItem.program || null,
    targetAgent: validAgent,
    onSubmitted,
    onClose: () => setConfirm(false),
  });
  const item = {
    title:
      activeDocument?.lessonTitle ||
      activeDocument?.courseTitle ||
      activeItem.title ||
      activeDocument?.title ||
      "Course Module",
    course_code: activeItem.course_code || activeDocument?.courseCode,
    program: activeItem.program || activeDocument?.program,
    uploaded_at: activeItem.uploaded_at || activeDocument?.uploadedAt,
  };
  return (
    <>
      <ModuleSetupView
        agent={validAgent}
        item={item}
        fields={<EvaluationSetupFields setup={setup} />}
        onSelect={onSelect}
        canStart={setup.canSubmit}
        pending={setup.isPending}
        onStart={() => setConfirm(true)}
      />
      <ConfirmationModal
        isOpen={confirm}
        title={`Start ${setup.meta.shortLabel} evaluation?`}
        variant="primary"
        description={
          <div className="swp-confirmation">
            <p className="font-medium text-text">{item.title}</p>
            <p>
              {setup.program}
              {setup.curriculumId
                ? ` · ${setup.readyCurricula.find((c) => c.documentId === setup.curriculumId)?.title}`
                : " · Module text only"}
            </p>
            <p>
              This creates a new run. Previous results remain in Evaluation
              history.
            </p>
          </div>
        }
        confirmLabel={`Run ${setup.meta.shortLabel} Evaluation`}
        confirmDisabled={!setup.canSubmit}
        isPending={setup.isPending}
        error={setup.error}
        onConfirm={setup.submit}
        onClose={() => setConfirm(false)}
      />
    </>
  );
}
