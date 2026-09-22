// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SpecialistScoreboardPage } from "../SpecialistScoreboardPage";
import { documentsApi } from "@equiped/api-client";
import { evaluationApi } from "../../api/evaluation.api";
import type { ClientDocument } from "@equiped/types";
import type {
  EvaluationListItem,
  EvaluationResultsResponse,
} from "../../types";
import type { TargetAgent } from "@equiped/types";

const mockNavigate = vi.fn();

vi.mock("@tanstack/react-router", () => ({
  useParams: () => ({}),
  useNavigate: () => mockNavigate,
  Link: ({
    children,
    to,
    params,
  }: {
    children: React.ReactNode;
    to: string;
    params?: Record<string, string>;
  }) => {
    let href = to;
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        href = href.replace(`$${key}`, value);
      });
    }
    return <a href={href}>{children}</a>;
  },
}));

vi.mock("@equiped/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@equiped/api-client")>();
  return {
    ...actual,
    documentsApi: {
      listDocuments: vi.fn(),
      getDocument: vi.fn(),
      getCurriculumSuggestion: vi.fn(),
    },
  };
});

vi.mock("../../api/evaluation.api", () => ({
  evaluationApi: {
    listEvaluations: vi.fn(),
    getEvaluationResults: vi.fn(),
    getDeskQueue: vi.fn(),
    submitEvaluation: vi.fn(),
    submitCriterionFeedback: vi.fn(),
  },
}));

const mockDoc: ClientDocument = {
  documentId: "doc-slm-001",
  title: "Data Structures SLM",
  courseTitle: "Data Structures",
  lessonTitle: "Module 1 - Arrays and Lists",
  academicYear: "2025-2026",
  courseCode: "CS101",
  pageCount: 15,
  hasOcrPages: false,
  chunks: [],
  program: "BSCS",
  sourceType: "slm",
  uploadedAt: "2026-08-20T10:00:00Z",
  processingStatus: "PROCESSED",
};

function renderPage(
  props: { agentId?: TargetAgent; documentId?: string } = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <SpecialistScoreboardPage {...props} />
    </QueryClientProvider>,
  );
}

describe("SpecialistScoreboardPage", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.mocked(documentsApi.listDocuments).mockReset();
    vi.mocked(documentsApi.getDocument).mockReset();
    vi.mocked(documentsApi.getCurriculumSuggestion).mockReset();
    vi.mocked(evaluationApi.listEvaluations).mockReset();
    vi.mocked(evaluationApi.getEvaluationResults).mockReset();
    vi.mocked(evaluationApi.getDeskQueue).mockReset();
    vi.mocked(evaluationApi.submitEvaluation).mockReset();
    vi.mocked(evaluationApi.submitCriterionFeedback).mockReset();
    mockNavigate.mockReset();

    vi.mocked(documentsApi.getCurriculumSuggestion).mockResolvedValue({
      documentId: "doc-slm-001",
      detectedProgram: "BSCS",
      selectedProgram: "BSCS",
      detectedCourseCode: "CS101",
      detectedAcademicYear: "2025-2026",
      detectedLessonTitle: "Module 1",
      preferredSuggestion: null,
      curriculumSuggestions: [],
      unavailableCurricula: [],
    });

    vi.mocked(documentsApi.getDocument).mockImplementation(async (id: string) => {
      if (id === mockDoc.documentId) {
        return mockDoc;
      }
      throw new Error("Document not found");
    });

    vi.mocked(evaluationApi.getDeskQueue).mockResolvedValue({
      items: [
        {
          document_id: "doc-slm-001",
          title: "Data Structures SLM",
          course_code: "CS101",
          program: "BSCS",
          uploaded_at: "2026-08-20T10:00:00Z",
          my_status: "READY",
          my_score: null,
          my_adjectival: null,
          peer_completed_count: 0,
          peer_completed_desks: [],
        },
      ],
      total: 1,
    });

    vi.mocked(documentsApi.listDocuments).mockResolvedValue({
      items: [mockDoc],
      total: 1,
      page: 1,
      pageSize: 100,
    });

    vi.mocked(evaluationApi.listEvaluations).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 5,
    });
  });

  it("renders the course modules list for /specialists/$agentId", async () => {
    renderPage({ agentId: "sme" });

    // Wait for the workstation to appear
    await waitFor(() => {
      expect(screen.getByText(/Choose a module to begin/i)).toBeDefined();
    });

    // Modules list is now in a modal, open it by clicking CTA
    const evaluateBtn = screen.getByRole("button", {
      name: /Start New Evaluation/i,
    });
    expect(evaluateBtn).toBeDefined();

    fireEvent.click(evaluateBtn);

    // Modal opens
    await waitFor(() => {
      expect(screen.getByText("Choose an unevaluated module")).toBeDefined();
      expect(screen.getAllByText("Data Structures SLM").length).toBeGreaterThan(
        0,
      );
      expect(screen.getByText("Ready")).toBeDefined();
    });

    // Click the document button
    const docBtn = screen.getByRole("button", { name: /Data Structures SLM/i });
    expect(docBtn).toBeDefined();
    fireEvent.click(docBtn);

    expect(mockNavigate).toHaveBeenCalledWith({
      to: "/specialists/$agentId/$documentId",
      params: { agentId: "sme", documentId: "doc-slm-001" },
    });
  });

  it("shows a completed empty state when every stored module is evaluated for the desk", async () => {
    vi.mocked(evaluationApi.getDeskQueue).mockResolvedValue({
      items: [
        {
          document_id: "doc-slm-001",
          title: "Data Structures SLM",
          course_code: "CS101",
          program: "BSCS",
          uploaded_at: "2026-08-20T10:00:00Z",
          my_status: "COMPLETED",
          my_score: 3.8,
          my_adjectival: "Very Satisfactory",
          peer_completed_count: 0,
          peer_completed_desks: ["sme"],
        },
      ],
      total: 1,
    });

    renderPage({ agentId: "sme" });

    await waitFor(() => {
      expect(screen.getByText("No modules awaiting review")).toBeDefined();
    });
    expect(
      screen.queryByRole("button", { name: /Start New Evaluation/i }),
    ).toBeNull();
  });

  it("renders unevaluated launchpad when documentId is provided in route", async () => {
    renderPage({ agentId: "sme", documentId: "doc-slm-001" });

    await waitFor(() => {
      expect(screen.getByText("Output preview")).toBeDefined();
      expect(screen.getByText("Unevaluated")).toBeDefined();
    });

    const launchBtn = screen.getByRole("button", {
      name: /Launch review/i,
    });
    expect(launchBtn).toBeDefined();

    // Clicking launch opens EvaluationConfirmModal
    fireEvent.click(launchBtn);
    await waitFor(() => {
      expect(screen.getByText("Confirm Targeted Evaluation")).toBeDefined();
      expect(screen.getByRole("dialog")).toBeDefined();
    });
  });

  it("renders completed results scoreboard with scores, criteria table, and quoted evidence", async () => {
    vi.mocked(evaluationApi.getDeskQueue).mockResolvedValue({
      items: [
        {
          document_id: "doc-slm-001",
          title: "Data Structures SLM",
          course_code: "CS101",
          program: "BSCS",
          uploaded_at: "2026-08-20T10:00:00Z",
          my_status: "COMPLETED",
          my_score: 3.8,
          my_adjectival: "Very Satisfactory",
          peer_completed_count: 2,
          peer_completed_desks: ["sme"],
        },
      ],
      total: 1,
    });

    vi.mocked(evaluationApi.listEvaluations).mockResolvedValue({
      items: [
        {
          evaluation_id: "eval-sme-101",
          document_id: "doc-slm-001",
          status: "COMPLETED",
          target_agent: "sme",
          submitted_at: "2026-09-08T00:00:00Z",
          completed_at: "2026-09-08T00:01:00Z",
        } as unknown as EvaluationListItem,
      ],
      total: 1,
      page: 1,
      page_size: 5,
    });

    const mockResults: EvaluationResultsResponse = {
      evaluation_id: "eval-sme-101",
      document_id: "doc-slm-001",
      document_title: "Data Structures SLM",
      synthesized_score: 95,
      overall_score: 3.8,
      adjectival_rating: "Very Satisfactory",
      active_agents: ["sme"],
      failed_agents: [],
      is_partial: false,
      evaluation_status: "COMPLETED",
      submitted_at: "2026-09-08T00:00:00Z",
      completed_at: "2026-09-08T00:01:00Z",
      flags: [],
      domain_scores: {
        sme: {
          subtotal: 3.8,
          max_score: 4,
          status: "COMPLETED",
          adjectival_rating: "Very Satisfactory",
          summary:
            "Strong discipline alignment and rigor across all data structure concepts.",
          criteria: [
            {
              criterion_id: "SME-01",
              criterion_text: "Content Accuracy and Depth",
              description: "Evaluates technical depth of data structures.",
              score: 3.8,
              justification:
                "The algorithms and data structure explanations are mathematically rigorous.",
              evidence:
                "Section 2.1 clearly demonstrates Big-O runtime analysis.",
              is_ungrounded: false,
              reviewer_correction: null,
            },
            {
              criterion_id: "SME-02",
              criterion_text: "Pedagogical Sequencing",
              description: "Evaluates progression of laboratory exercises.",
              score: 3.5,
              justification:
                "Topics flow logically from arrays to linked lists.",
              evidence:
                "Chapter transition on page 8 bridges primitive arrays to dynamic nodes.",
              is_ungrounded: false,
              reviewer_correction: {
                action: "EDIT",
                score: 4.0,
                justification:
                  "Human reviewer confirmed superior sequencing in laboratory exercises.",
              },
            },
          ],
        },
      },
    };

    vi.mocked(evaluationApi.getEvaluationResults).mockResolvedValue(
      mockResults,
    );

    renderPage({ agentId: "sme", documentId: "doc-slm-001" });

    await waitFor(() => {
      expect(
        screen.getByRole("heading", {
          name: /Subject Matter Expert \(SME\) Performance Score/i,
        }),
      ).toBeDefined();
    });

    expect(screen.getAllByText("3.80 / 4").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Very Satisfactory").length).toBeGreaterThan(0);
    expect(screen.getByText(/95% Compliance/i)).toBeDefined();
    const summaryDetails = screen
      .getByText("Specialist summary")
      .closest("details")!;
    expect(summaryDetails.open).toBe(false);
    fireEvent.click(summaryDetails.querySelector("summary")!);
    expect(
      screen.getByText(
        /Strong discipline alignment and rigor across all data structure concepts\./i,
      ),
    ).toBeDefined();
    fireEvent.click(summaryDetails.querySelector("summary")!);

    // Action Toolbar buttons
    expect(
      screen.getByRole("button", { name: /Review scores/i }),
    ).toBeDefined();
    expect(
      screen.getByRole("button", { name: /Download PDF - SME Scorecard/i }),
    ).toBeDefined();
    expect(screen.getByText(/Download SME PDF/i)).toBeDefined();
    expect(screen.getByRole("button", { name: /Re-evaluate/i })).toBeDefined();

    // Evidence-led criteria review
    expect(
      screen.getByRole("heading", { name: /Criteria breakdown/i }),
    ).toBeDefined();
    expect(screen.queryByText("Criterion 1")).toBeNull();
    expect(
      screen.getAllByRole("heading", { name: mockDoc.lessonTitle! }).length,
    ).toBe(1);
    const firstCriterion = screen.getByText("SME-01").closest("details")!;
    const secondCriterion = screen.getByText("SME-02").closest("details")!;
    expect(firstCriterion.open).toBe(false);
    expect(secondCriterion.open).toBe(false);
    expect(
      screen.getByText("Reviewer correction").closest("summary"),
    ).not.toBeNull();
    fireEvent.click(firstCriterion.querySelector("summary")!);
    expect(firstCriterion.open).toBe(true);
    expect(screen.getAllByText("Score").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Specialist finding").length).toBeGreaterThan(0);

    // Criterion 1 row with SLM quoted evidence
    expect(screen.getByText("SME-01")).toBeDefined();
    expect(screen.getByText("Content Accuracy and Depth")).toBeDefined();
    expect(screen.getAllByText("SLM evidence").length).toBeGreaterThan(0);
    expect(
      screen.getByText(
        /Section 2\.1 clearly demonstrates Big-O runtime analysis\./i,
      ),
    ).toBeDefined();
    fireEvent.click(firstCriterion.querySelector("summary")!);
    expect(firstCriterion.open).toBe(false);

    // Criterion 2 row with Human Reviewer Override Callout
    expect(screen.getByText("SME-02")).toBeDefined();
    expect(screen.getByText("Pedagogical Sequencing")).toBeDefined();
    fireEvent.click(secondCriterion.querySelector("summary")!);
    expect(screen.getByText(/CID reviewer override/i)).toBeDefined();

    // Breadcrumb and SLM Storage links
    expect(screen.getByText("Back to SME Desk")).toBeDefined();
    expect(screen.getAllByText("View in SLM Storage").length).toBeGreaterThan(0);
    expect(screen.getAllByText("SLM Storage").length).toBeGreaterThan(0);

    // Criteria triage filters
    expect(screen.getByRole("button", { name: /All \(2\)/i })).toBeDefined();
    expect(screen.getByRole("button", { name: /Strong \(2\)/i })).toBeDefined();
    const correctedTab = screen.getByRole("button", { name: /Corrected \(1\)/i });
    expect(correctedTab).toBeDefined();

    // Filter by Corrected: only SME-02 remains
    fireEvent.click(correctedTab);
    expect(screen.queryByText("SME-01")).toBeNull();
    expect(screen.getByText("SME-02")).toBeDefined();

    // Reset back to All
    const allTab = screen.getByRole("button", { name: /All \(2\)/i });
    fireEvent.click(allTab);
    expect(screen.getByText("SME-01")).toBeDefined();
    expect(screen.getByText("SME-02")).toBeDefined();
  });

  it("shows a retry state when completed specialist results cannot be retrieved", async () => {
    vi.mocked(evaluationApi.getDeskQueue).mockResolvedValue({
      items: [
        {
          document_id: "doc-slm-001",
          title: "Data Structures SLM",
          course_code: "CS101",
          program: "BSCS",
          uploaded_at: "2026-08-20T10:00:00Z",
          my_status: "COMPLETED",
          my_score: 3.8,
          my_adjectival: "Very Satisfactory",
          peer_completed_count: 0,
          peer_completed_desks: ["sme"],
        },
      ],
      total: 1,
    });
    vi.mocked(evaluationApi.listEvaluations).mockResolvedValue({
      items: [
        {
          evaluation_id: "eval-sme-error",
          document_id: "doc-slm-001",
          status: "COMPLETED",
          target_agent: "sme",
          submitted_at: "2026-09-08T00:00:00Z",
        } as unknown as EvaluationListItem,
      ],
      total: 1,
      page: 1,
      page_size: 5,
    });
    vi.mocked(evaluationApi.getEvaluationResults).mockRejectedValue(
      new Error("Temporary results outage"),
    );

    renderPage({ agentId: "sme", documentId: "doc-slm-001" });

    expect(
      await screen.findByText("Specialist results could not be loaded"),
    ).toBeDefined();
    expect(screen.getByRole("button", { name: "Try again" })).toBeDefined();
  });

  it("keeps unevaluated launchpad when a completed evaluation exists for a different desk (multi-permission account)", async () => {
    vi.mocked(evaluationApi.getDeskQueue).mockResolvedValue({
      items: [
        {
          document_id: "doc-slm-001",
          title: "Data Structures SLM",
          course_code: "CS101",
          program: "BSCS",
          uploaded_at: "2026-08-20T10:00:00Z",
          my_status: "READY",
          my_score: null,
          my_adjectival: null,
          peer_completed_count: 1,
          peer_completed_desks: ["coordinator"],
        },
      ],
      total: 1,
    });
    // If query returns coordinator jobs, it must be filtered out for SME
    vi.mocked(evaluationApi.listEvaluations).mockResolvedValue({
      items: [
        {
          evaluation_id: "eval-coord-101",
          document_id: "doc-slm-001",
          status: "COMPLETED",
          target_agent: "coordinator",
          submitted_at: "2026-09-08T00:00:00Z",
        } as unknown as EvaluationListItem,
      ],
      total: 1,
      page: 1,
      page_size: 5,
    });

    renderPage({ agentId: "sme", documentId: "doc-slm-001" });

    // Must verify listEvaluations was called with the specific desk targetAgent
    await waitFor(() => {
      expect(evaluationApi.listEvaluations).toHaveBeenCalledWith(
        "doc-slm-001",
        "sme",
      );
    });

    // Must show the Unevaluated launchpad, NOT the completed scoreboard!
    await waitFor(() => {
      expect(screen.getByText(/Unevaluated/i)).toBeDefined();
      expect(
        screen.getByRole("button", { name: /Launch review/i }),
      ).toBeDefined();
    });

    expect(
      screen.queryByRole("heading", {
        name: /Subject Matter Expert \(SME\) Performance Score/i,
      }),
    ).toBeNull();
  });

  it("renders badges: Ready and Evaluating for pending modules in personal storage", async () => {
    vi.mocked(evaluationApi.getDeskQueue).mockResolvedValue({
      items: [
        {
          document_id: "doc-slm-001",
          title: "Module 1 - Ready",
          course_code: "CS101",
          program: "BSCS",
          uploaded_at: "2026-08-20T10:00:00Z",
          my_status: "READY",
          my_score: null,
          my_adjectival: null,
          peer_completed_count: 0,
          peer_completed_desks: [],
        },
        {
          document_id: "doc-slm-002",
          title: "Module 2 - Evaluating",
          course_code: "CS102",
          program: "BSCS",
          uploaded_at: "2026-08-21T10:00:00Z",
          my_status: "EVALUATING",
          my_score: null,
          my_adjectival: null,
          peer_completed_count: 0,
          peer_completed_desks: [],
        },
      ],
      total: 2,
    });

    renderPage({ agentId: "sme" });

    await waitFor(() => {
      expect(screen.getByText("Module 2 - Evaluating")).toBeDefined();
      expect(screen.getAllByText(/Evaluating/i).length).toBeGreaterThan(0);
    });

    const evaluateBtn = screen.getByRole("button", {
      name: /Start New Evaluation/i,
    });
    fireEvent.click(evaluateBtn);

    await waitFor(() => {
      expect(screen.getAllByText("Module 1 - Ready").length).toBeGreaterThan(0);
      expect(screen.getByText("Ready")).toBeDefined();
    });
  });
  it("renders live progress indicator when evaluation is in progress", async () => {
    vi.mocked(evaluationApi.getDeskQueue).mockResolvedValue({
      items: [
        {
          document_id: "doc-slm-001",
          title: "Data Structures SLM",
          course_code: "CS101",
          program: "BSCS",
          uploaded_at: "2026-08-20T10:00:00Z",
          my_status: "EVALUATING",
          my_score: null,
          my_adjectival: null,
          peer_completed_count: 0,
          peer_completed_desks: [],
        },
      ],
      total: 1,
    });

    vi.mocked(evaluationApi.listEvaluations).mockResolvedValue({
      items: [
        {
          evaluation_id: "eval-sme-progress",
          document_id: "doc-slm-001",
          status: "EVALUATING",
          target_agent: "sme",
          submitted_at: "2026-09-08T00:00:00Z",
        } as unknown as EvaluationListItem,
      ],
      total: 1,
      page: 1,
      page_size: 5,
    });

    renderPage({ agentId: "sme", documentId: "doc-slm-001" });

    await waitFor(() => {
      expect(
        screen.getByRole("heading", {
          name: /Subject Matter Expert \(SME\) Evaluation in Progress/i,
        }),
      ).toBeDefined();
    });

    expect(screen.getByText(/Status: EVALUATING/i)).toBeDefined();
  });

  it("renders GAD review and role specific details when agentId is gad", async () => {
    vi.mocked(evaluationApi.getDeskQueue).mockResolvedValue({
      items: [
        {
          document_id: "doc-slm-001",
          title: "Data Structures SLM",
          course_code: "CS101",
          program: "BSCS",
          uploaded_at: "2026-08-20T10:00:00Z",
          my_status: "COMPLETED",
          my_score: 3.8,
          my_adjectival: "Very Satisfactory",
          peer_completed_count: 1,
          peer_completed_desks: ["gad"],
        },
      ],
      total: 1,
    });

    vi.mocked(evaluationApi.listEvaluations).mockResolvedValue({
      items: [
        {
          evaluation_id: "eval-gad-101",
          document_id: "doc-slm-001",
          status: "COMPLETED",
          target_agent: "gad",
          submitted_at: "2026-09-08T00:00:00Z",
        } as unknown as EvaluationListItem,
      ],
      total: 1,
      page: 1,
      page_size: 5,
    });

    vi.mocked(evaluationApi.getEvaluationResults).mockResolvedValue({
      evaluation_id: "eval-gad-101",
      document_id: "doc-slm-001",
      synthesized_score: 95,
      overall_score: 3.8,
      adjectival_rating: "Very Satisfactory",
      active_agents: ["gad"],
      failed_agents: [],
      is_partial: false,
      evaluation_status: "COMPLETED",
      domain_scores: {
        gad: {
          subtotal: 3.8,
          max_score: 4,
          status: "COMPLETED",
          adjectival_rating: "Very Satisfactory",
          summary: "GAD summary",
          criteria: [],
        },
      },
      flags: [],
    });

    renderPage({ agentId: "gad", documentId: "doc-slm-001" });

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /GAD Unit Performance Score/i }),
      ).toBeDefined();
    });
  });

  it("incorporates owned doc outside initial pages into workspace model and displays it", async () => {
    // Initial storage list does not contain doc-outside-001
    vi.mocked(documentsApi.listDocuments).mockResolvedValue({
      items: [mockDoc],
      total: 105,
      page: 1,
      pageSize: 100,
    });
    vi.mocked(evaluationApi.getDeskQueue).mockResolvedValue({
      items: [
        {
          document_id: "doc-outside-001",
          title: "Module on Page 2",
          course_code: "CS102",
          program: "BSCS",
          uploaded_at: "2026-08-20T10:00:00Z",
          my_status: "READY",
          my_score: null,
          my_adjectival: null,
          peer_completed_count: 0,
          peer_completed_desks: [],
        },
      ],
      total: 1,
    });

    const outsideDoc: ClientDocument = {
      ...mockDoc,
      documentId: "doc-outside-001",
      title: "Module on Page 2",
      courseTitle: null,
      lessonTitle: null,
    };

    vi.mocked(documentsApi.getDocument).mockImplementation(async (id: string) => {
      if (id === "doc-outside-001") return outsideDoc;
      return mockDoc;
    });

    vi.mocked(evaluationApi.listEvaluations).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 5,
    });

    renderPage({ agentId: "sme", documentId: "doc-outside-001" });

    await waitFor(() => {
      expect(documentsApi.getDocument).toHaveBeenCalledWith("doc-outside-001");
      expect(evaluationApi.getDeskQueue).toHaveBeenCalledWith("sme", undefined, "doc-outside-001");
    });

    await waitFor(() => {
      expect(screen.getByText("Module on Page 2")).toBeDefined();
      expect(screen.getByText(/Unevaluated/i)).toBeDefined();
    });

    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("redirects to specialist index when queue is empty and route document is invalid", async () => {
    vi.mocked(documentsApi.listDocuments).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      pageSize: 100,
    });
    vi.mocked(evaluationApi.getDeskQueue).mockResolvedValue({
      items: [],
      total: 0,
    });
    vi.mocked(documentsApi.getDocument).mockRejectedValue(new Error("Document not found"));

    renderPage({ agentId: "sme", documentId: "doc-nonexistent" });

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({
        to: "/specialists/$agentId",
        params: { agentId: "sme" },
      });
    });
  });

  it("redirects when document is inaccessible or has incorrect source/status", async () => {
    // Case 1: Inaccessible (403/error)
    vi.mocked(documentsApi.listDocuments).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      pageSize: 100,
    });
    vi.mocked(evaluationApi.getDeskQueue).mockResolvedValue({
      items: [],
      total: 0,
    });
    vi.mocked(documentsApi.getDocument).mockRejectedValue(new Error("Forbidden"));

    const { unmount } = renderPage({ agentId: "sme", documentId: "doc-forbidden" });

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({
        to: "/specialists/$agentId",
        params: { agentId: "sme" },
      });
    });

    unmount();
    mockNavigate.mockReset();

    // Case 2: Incorrect source type (syllabus instead of slm)
    const syllabusDoc: ClientDocument = {
      ...mockDoc,
      documentId: "doc-syllabus",
      sourceType: "syllabus" as ClientDocument["sourceType"],
    };
    vi.mocked(documentsApi.getDocument).mockResolvedValue(syllabusDoc);

    const { unmount: unmount2 } = renderPage({ agentId: "sme", documentId: "doc-syllabus" });

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({
        to: "/specialists/$agentId",
        params: { agentId: "sme" },
      });
    });

    unmount2();
    mockNavigate.mockReset();

    // Case 3: Ineligible processingStatus (PROCESSING instead of PROCESSED)
    const unprocessedDoc: ClientDocument = {
      ...mockDoc,
      documentId: "doc-processing",
      processingStatus: "PROCESSING" as ClientDocument["processingStatus"],
    };
    vi.mocked(documentsApi.getDocument).mockResolvedValue(unprocessedDoc);

    renderPage({ agentId: "sme", documentId: "doc-processing" });

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({
        to: "/specialists/$agentId",
        params: { agentId: "sme" },
      });
    });
  });
});
