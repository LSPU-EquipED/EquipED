import type { TargetAgent } from "@equiped/types";

/** Ordered server stages and their current workspace presentation. */
export const EVALUATION_STAGES = [
  {
    status: "SUBMITTED",
    label: "Queued",
    heading: "Your module is in the queue.",
    description: "The evaluation will begin when the specialist is available.",
  },
  {
    status: "PREPROCESSING",
    label: "Preparation",
    heading: "Preparing your module.",
    description:
      "Organizing the module text and the references needed for this review.",
  },
  {
    status: "EVALUATING",
    label: "Specialist review",
    heading: "A closer look at your material.",
    description:
      "Examining the module against the specialist rubric and collecting supporting evidence.",
  },
  {
    status: "SYNTHESIZING",
    label: "Finalizing",
    heading: "Bringing the findings together.",
    description:
      "Saving the specialist findings and updating the monitoring record.",
  },
] as const;

export type ActiveStage = (typeof EVALUATION_STAGES)[number]["status"];

export function isActiveEvaluationStatus(
  status?: string,
): status is ActiveStage {
  return EVALUATION_STAGES.some((stage) => stage.status === status);
}

export const SPECIALIST_REVIEW_COPY: Record<TargetAgent, string> = {
  sme: "The SME specialist is checking content accuracy and instructional quality, with evidence from your module to support each finding.",
  coordinator:
    "The Coordinator specialist is checking curriculum alignment, using your module and its verified curriculum reference to support each finding.",
  gad: "The GAD specialist is checking inclusivity and gender responsiveness, with evidence from your module to support each finding.",
  itso: "The ITSO specialist is checking intellectual property, citation practice, and data privacy, with evidence from your module to support each finding.",
};
