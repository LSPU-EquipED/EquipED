import { ConfirmationModal } from "@equiped/ui";
import {
  useEvaluationSetup,
  type EvaluationSetupOptions,
} from "../../hooks/useEvaluationSetup";
import { EvaluationSetupFields } from "./EvaluationSetupFields";
import "../../styles/specialist-workspace.css";

export interface EvaluationConfirmModalProps extends EvaluationSetupOptions {
  documentTitle: string;
  onClose: () => void;
}

export function EvaluationConfirmModal(props: EvaluationConfirmModalProps) {
  const setup = useEvaluationSetup(props);
  return (
    <ConfirmationModal
      isOpen
      title={`Start ${setup.meta.shortLabel} evaluation?`}
      variant="primary"
      description={
        <div className="swp-confirmation">
          <p className="font-medium text-text">{props.documentTitle}</p>
          <p>{setup.meta.requirement}</p>
          <EvaluationSetupFields setup={setup} />
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
      onClose={props.onClose}
    />
  );
}
