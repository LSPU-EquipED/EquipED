/** Labels for the selected specialist's module browser, not overall module completion. */
export function specialistModuleState(status: string | null | undefined) {
  switch (status?.toUpperCase()) {
    case "COMPLETED":
      return {
        status: "COMPLETED",
        label: "Completed",
        action: "View results",
        color: "text-success",
      };
    case "FAILED":
      return {
        status: "FAILED",
        label: "Failed",
        action: "Inspect evaluation",
        color: "text-destructive",
      };
    case "SUBMITTED":
    case "PREPROCESSING":
    case "EVALUATING":
    case "SYNTHESIZING":
      return {
        status: "EVALUATING",
        label: "Evaluating",
        action: "View progress",
        color: "text-info",
      };
    default:
      return {
        status: "READY",
        label: "Not evaluated",
        action: "Evaluate",
        color: "text-text-muted",
      };
  }
}
