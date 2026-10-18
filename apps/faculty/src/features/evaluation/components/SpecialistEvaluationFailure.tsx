import { WorkspaceRecovery } from "./workspace/WorkspaceStates";
import "../styles/specialist-workspace.css";
interface SpecialistEvaluationFailureProps {
  errorMessage?: string | null;
  documentTitle?: string;
  onRetry: () => void;
}
export function SpecialistEvaluationFailure({
  errorMessage,
  documentTitle,
  onRetry,
}: SpecialistEvaluationFailureProps) {
  return (
    <WorkspaceRecovery
      kind="evaluation"
      item={documentTitle ? { title: documentTitle } : undefined}
      errorMessage={errorMessage}
      onRetry={onRetry}
    />
  );
}
