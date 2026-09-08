import { isLspuSccProgram, normalizeProgram } from '@/shared/constants/programs';
import { isTargetAgent, type TargetAgent } from '@/shared/types/evaluations';
import type { EvaluationSubmitRequest } from '../types';

export { normalizeProgram };

export interface EvaluationSubmitParams {
  documentId: string;
  program: string;
  targetAgent: TargetAgent;
  curriculumId?: string | null;
}

/**
 * Builds the submission payload for a targeted single-agent evaluation.
 * Enforces canonical program validation and Coordinator curriculum prerequisites.
 * GAD, ITSO, and SME evaluate SLM document text directly with zero curriculum gating.
 */
export function buildEvaluationSubmitPayload({
  documentId,
  program,
  targetAgent,
  curriculumId,
}: EvaluationSubmitParams): EvaluationSubmitRequest {
  if (!isTargetAgent(targetAgent)) {
    throw new Error(
      `Invalid target agent '${targetAgent}'. Must be one of 'sme', 'coordinator', 'gad', or 'itso'.`,
    );
  }
  if (!program || !isLspuSccProgram(program)) {
    throw new Error(
      `Invalid program '${program}'. Must be a supported LSPU SCC program ('BSCS' or 'BSInfoTech').`,
    );
  }

  const confirmed_program = normalizeProgram(program);

  if (targetAgent === 'coordinator') {
    if (!curriculumId || curriculumId.trim().length === 0) {
      throw new Error('Curriculum context is required for Program Coordinator evaluation');
    }
    return {
      document_id: documentId,
      curriculum_id: curriculumId.trim(),
      target_agent: targetAgent,
      confirmed_program,
      partial_without_curriculum: false,
    };
  }

  return {
    document_id: documentId,
    target_agent: targetAgent,
    confirmed_program,
    partial_without_curriculum: false,
  };
}

/** Backward-compatible export alias. */
export const buildTargetedEvaluationSubmitPayload = buildEvaluationSubmitPayload;
