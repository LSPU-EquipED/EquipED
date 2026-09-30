import type { TargetAgent } from "@equiped/types";

export const EVALUATION_STAGES = [
  {
    status: "SUBMITTED",
    label: "Queued",
    heading: "Your evaluation is queued",
    description:
      "Your module is waiting for evaluation to begin. This page updates automatically when the job starts.",
  },
  {
    status: "PREPROCESSING",
    label: "Preparation",
    heading: "Preparing your learning material",
    description:
      "Preparing the SLM and evaluation context for specialist review.",
  },
  {
    status: "EVALUATING",
    label: "Specialist review",
    heading: "Reviewing your learning material",
  },
  {
    status: "SYNTHESIZING",
    label: "Finalizing",
    heading: "Finalizing your evaluation",
    description:
      "Saving the evaluation findings and updating the monitoring matrix.",
  },
];

export function isActiveEvaluationStatus(status?: string): boolean {
  return EVALUATION_STAGES.some((stage) => stage.status === status);
}

export const SPECIALIST_REVIEW_COPY: Record<TargetAgent, string> = {
  sme: "The SME specialist is checking content accuracy and instructional quality, with evidence from your module to support each finding.",
  coordinator:
    "The Coordinator specialist is checking curriculum alignment, using your module and its verified curriculum reference to support each finding.",
  gad: "The GAD specialist is checking inclusivity and gender responsiveness, with evidence from your module to support each finding.",
  itso: "The ITSO specialist is checking intellectual property, citation practice, and data privacy, with evidence from your module to support each finding.",
};
