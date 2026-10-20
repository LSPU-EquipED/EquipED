import { requestJson } from "./http";
import { parseAssessment, type AssessmentRead } from "@equiped/types";

/** Historical evidence-only reads; current ITSO runs use the normal evaluation API. */
export const itsoApi = {
  async getAssessment(
    evaluationId: string,
    signal?: AbortSignal,
  ): Promise<AssessmentRead> {
    return parseAssessment(
      await requestJson<unknown>(
        `/evaluations/${encodeURIComponent(evaluationId)}/assessment`,
        { signal },
      ),
    );
  },
};
