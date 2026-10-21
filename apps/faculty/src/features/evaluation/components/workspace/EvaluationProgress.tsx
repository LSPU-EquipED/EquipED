import { Check } from "@phosphor-icons/react";
import { TARGET_AGENT_META, type TargetAgent } from "@equiped/types";
import {
  EVALUATION_STAGES,
  SPECIALIST_REVIEW_COPY,
} from "../../utils/evaluationProgress";
import { StageArtwork } from "./StageArtwork";
import "../../styles/specialist-workspace.css";

interface EvaluationProgressProps {
  status?: string;
  targetAgent?: TargetAgent | "all";
  documentTitle?: string;
}
/** Stage changes remain driven solely by the server, including unknown admission status. */
export function EvaluationProgress({
  status,
  targetAgent,
  documentTitle,
}: EvaluationProgressProps) {
  const index = EVALUATION_STAGES.findIndex((stage) => stage.status === status);
  const presentation = EVALUATION_STAGES[index];
  const stage = presentation?.status;
  const specialist =
    targetAgent && targetAgent !== "all"
      ? TARGET_AGENT_META[targetAgent].shortLabel
      : targetAgent === "all"
        ? "Specialist team"
        : "Specialist";
  const description =
    status === "EVALUATING"
      ? targetAgent && targetAgent !== "all"
        ? SPECIALIST_REVIEW_COPY[targetAgent]
        : "The specialists are reviewing your module against the applicable rubrics, with evidence to support each finding."
      : presentation?.description || "Waiting for the latest evaluation stage.";
  return (
    <section
      className="swp-progress"
      aria-label={
        documentTitle
          ? `Evaluation progress for ${documentTitle}`
          : "Evaluation progress"
      }
    >
      <div className="swp-progress-context">
        {documentTitle && <span>{documentTitle}</span>}
        <span>
          {specialist}
          {targetAgent !== "all" ? " evaluation" : ""}
        </span>
      </div>
      <div className="swp-progress-body">
        <div
          className="swp-progress-copy"
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          <span className="swp-stage-label">
            {stage ? (
              <>
                Step {index + 1} of 4 <span aria-hidden="true">/</span>{" "}
                {presentation?.label}
              </>
            ) : (
              "Updating status"
            )}
          </span>
          <h1>{presentation?.heading || "Checking evaluation status"}</h1>
          <p>{description}</p>
        </div>
        <StageArtwork stage={stage} />
      </div>
      <ol className="swp-stages" aria-label="Evaluation stages">
        {EVALUATION_STAGES.map((step, i) => (
          <li
            key={step.status}
            aria-current={i === index ? "step" : undefined}
            className={i < index ? "is-done" : i === index ? "is-current" : ""}
          >
            <span className="swp-step-number" aria-hidden="true">
              {i < index ? <Check size={15} weight="bold" /> : `0${i + 1}`}
            </span>
            <span>
              {step.label}
              <span className="sr-only">
                {i < index
                  ? ", done"
                  : i === index
                    ? ", in progress"
                    : ", pending"}
              </span>
            </span>
          </li>
        ))}
      </ol>
      <p className="swp-progress-footer">
        You can leave this page. The evaluation continues in the background.
      </p>
    </section>
  );
}
