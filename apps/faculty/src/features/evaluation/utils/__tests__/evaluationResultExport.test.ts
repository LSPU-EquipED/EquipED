import { describe, expect, it } from "vitest";
import type { ClientDocument } from "@equiped/types";
import type { DomainScoreBlock, EvaluationResultsResponse } from "../../types";
import { buildEvaluationResultExport } from "../evaluationResultExport";

const results: EvaluationResultsResponse = {
  evaluation_id: "saved-evaluation",
  document_id: "saved-document",
  synthesized_score: 90,
  domain_scores: {},
  flags: [],
  active_agents: ["coordinator"],
  failed_agents: [],
  is_partial: true,
  partial_reason: "Curriculum unavailable",
  evaluation_status: "COMPLETED",
};

const domainScore: DomainScoreBlock = {
  criteria: [
    {
      criterion_id: "B-02",
      criterion_text: "Second criterion",
      score: 3,
      justification: "Recorded second score",
      display_order: 2,
    },
    {
      criterion_id: "A-01",
      criterion_text: "First criterion",
      score: 4,
      justification: "Recorded first score",
      display_order: 1,
    },
  ],
  subtotal: 7,
  max_score: 8,
  status: "SAVED_STATUS",
  adjectival_rating: "Very Satisfactory",
  summary: "Saved summary",
  version: 5,
  form_snapshot_id: "saved-form-snapshot",
};

const activeDocument: ClientDocument = {
  documentId: "active-document",
  title: "Document title",
  courseTitle: "Course",
  lessonTitle: "Lesson",
  sourceType: "slm",
  program: "Document program",
  academicYear: null,
  courseCode: "D-1",
  pageCount: null,
  processingStatus: "PROCESSED",
  hasOcrPages: false,
  uploadedAt: "2026-10-01",
  chunks: [],
};

describe("buildEvaluationResultExport", () => {
  it("uses the export title fallback precedence separately from visible lesson/course titles", () => {
    const fromResults = buildEvaluationResultExport({
      agentId: "coordinator",
      evaluationId: "saved-evaluation",
      results: { ...results, document_title: "Saved result title" },
      domainScore,
      criteria: domainScore.criteria,
      activeItem: {
        title: "Queue title",
        program: "Queue program",
        course_code: "Q-1",
      },
      activeDocument,
    });
    expect(fromResults.documentTitle).toBe("Saved result title");

    const fromQueue = buildEvaluationResultExport({
      agentId: "coordinator",
      evaluationId: "saved-evaluation",
      results,
      domainScore,
      criteria: domainScore.criteria,
      activeItem: { title: "Queue title", program: null, course_code: null },
      activeDocument,
    });
    expect(fromQueue.documentTitle).toBe("Queue title");

    const fromDocument = buildEvaluationResultExport({
      agentId: "coordinator",
      evaluationId: "saved-evaluation",
      results,
      domainScore,
      criteria: domainScore.criteria,
      activeItem: null,
      activeDocument,
    });
    expect(fromDocument.documentTitle).toBe("Document title");
    expect(
      buildEvaluationResultExport({
        agentId: "coordinator",
        evaluationId: "saved-evaluation",
        results,
        domainScore,
        criteria: domainScore.criteria,
        activeItem: null,
        activeDocument: null,
      }).documentTitle,
    ).toBe("Course Module");
  });

  it("preserves saved run provenance, official criteria, and score metadata", () => {
    const officialCriteria = [...domainScore.criteria].reverse();
    const document = null;
    const exported = buildEvaluationResultExport({
      agentId: "coordinator",
      evaluationId: "recorded-run-id",
      results,
      domainScore,
      criteria: officialCriteria,
      activeItem: null,
      activeDocument: document,
    });

    expect(exported).toMatchObject({
      agentId: "coordinator",
      evaluationId: "recorded-run-id",
      results,
      document,
      isPartial: true,
      partialReason: "Curriculum unavailable",
      evaluationStatus: "COMPLETED",
      subtotal: 7,
      max_score: 8,
      status: "SAVED_STATUS",
      adjectival_rating: "Very Satisfactory",
      summary: "Saved summary",
      version: 5,
      form_snapshot_id: "saved-form-snapshot",
    });
    expect(exported.criteria).toBe(officialCriteria);
    expect(
      exported.criteria.map((criterion) => criterion.criterion_id),
    ).toEqual(["A-01", "B-02"]);
  });

  it("retains null and empty optional metadata fallback semantics", () => {
    const exported = buildEvaluationResultExport({
      agentId: "sme",
      evaluationId: "saved-evaluation",
      results: { ...results, program: "" },
      domainScore: {
        ...domainScore,
        status: "",
        max_score: 0,
        adjectival_rating: null,
        form_snapshot_id: null,
      },
      criteria: [],
      activeItem: { title: "", program: "", course_code: "" },
      activeDocument: null,
    });

    expect(exported.documentTitle).toBe("Course Module");
    expect(exported.program).toBeNull();
    expect(exported.courseCode).toBeNull();
    expect(exported.max_score).toBe(4);
    expect(exported.status).toBe("COMPLETED");
    expect(exported.adjectival_rating).toBeUndefined();
    expect(exported.form_snapshot_id).toBeUndefined();
  });
});
