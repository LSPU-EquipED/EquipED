import type { TargetAgent } from "@equiped/types";
import contentArt from "../assets/workspace/illustrations/content-inspection.svg";
import curriculumArt from "../assets/workspace/illustrations/curriculum-planning.svg";
import inclusiveArt from "../assets/workspace/illustrations/inclusive-discussion.svg";
import innovationArt from "../assets/workspace/illustrations/innovation-workbench.svg";

export const specialistPresentation: Record<
  TargetAgent,
  {
    heading: string;
    description: string;
    focus: string[];
    image: string;
  }
> = {
  sme: {
    heading: "Content, considered closely.",
    description:
      "Examine the accuracy and instructional quality of your learning materials.",
    focus: ["Content accuracy", "Instructional quality", "Assessment"],
    image: contentArt,
  },
  coordinator: {
    heading: "Learning objectives, in context.",
    description:
      "Review your module alongside its verified curriculum reference.",
    focus: ["Learning objectives", "Assessment", "Curriculum alignment"],
    image: curriculumArt,
  },
  gad: {
    heading: "Make room for every learner.",
    description:
      "Examine language, representation, and inclusivity throughout your module.",
    focus: ["Inclusive language", "Representation", "Gender responsiveness"],
    image: inclusiveArt,
  },
  itso: {
    heading: "Original work, responsibly sourced.",
    description:
      "Review attribution, ownership, and data privacy in your learning materials.",
    focus: ["Source attribution", "Ownership", "Data privacy"],
    image: innovationArt,
  },
};
