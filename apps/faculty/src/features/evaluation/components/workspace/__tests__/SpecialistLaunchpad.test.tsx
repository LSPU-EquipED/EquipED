// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { documentsApi } from "@equiped/api-client";
import { type TargetAgent } from "@equiped/types";
import { SpecialistLaunchpad } from "../SpecialistLaunchpad";
import { evaluationApi } from "../../../api/evaluation.api";

vi.mock("../../../api/evaluation.api", () => ({
  evaluationApi: { submitEvaluation: vi.fn() },
}));
vi.mock("@equiped/api-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@equiped/api-client")>()),
  documentsApi: { getCurriculumSuggestion: vi.fn() },
}));

function renderSetup(agent: TargetAgent = "coordinator") {
  const onSubmitted = vi.fn();
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <SpecialistLaunchpad
        validAgent={agent}
        activeDocument={null}
        activeItem={{
          document_id: "doc-1",
          title: "Module 1",
          course_code: "CS101",
          uploaded_at: "2026-10-18T00:00:00Z",
          program: "BSCS",
          my_status: "READY",
          my_score: null,
          my_adjectival: null,
          peer_completed_count: 0,
          peer_completed_desks: [],
        }}
        onSubmitted={onSubmitted}
        onSelect={vi.fn()}
      />
    </QueryClientProvider>,
  );
  return { onSubmitted };
}

async function selectCurriculum() {
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: /Verified curriculum/ }),
    ).toBeDefined(),
  );
  fireEvent.click(screen.getByRole("button", { name: /Verified curriculum/ }));
  fireEvent.click(
    screen.getByRole("option", { name: "Verified curriculum 2026" }),
  );
}

describe("SpecialistLaunchpad admission", () => {
  beforeEach(() => {
    vi.mocked(documentsApi.getCurriculumSuggestion).mockResolvedValue({
      documentId: "doc-1",
      detectedProgram: "BSCS",
      selectedProgram: "BSCS",
      detectedCourseCode: "CS101",
      detectedAcademicYear: null,
      detectedLessonTitle: null,
      preferredSuggestion: null,
      unavailableCurricula: [],
      curriculumSuggestions: [
        {
          documentId: "curr-1",
          title: "Verified curriculum 2026",
          program: "BSCS",
          embeddingReady: true,
          matchReason: "selected_program",
        },
      ],
    });
    vi.mocked(evaluationApi.submitEvaluation).mockResolvedValue({
      evaluation_id: "eval-1",
      document_id: "doc-1",
      target_agent: "coordinator",
      status: "SUBMITTED",
      submitted_at: "2026-10-18T00:00:00Z",
    });
  });
  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
    vi.unstubAllGlobals();
  });

  it("uses the existing ITSO confirmation with required online checks and no opt-out", async () => {
    const { onSubmitted } = renderSetup("itso");
    expect(screen.queryByText(/Prepare source/)).toBeNull();
    expect(screen.queryByRole("checkbox")).toBeNull();
    expect(
      screen.getByText(/criteria 1 and 2 on every evaluation/),
    ).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Start evaluation" }));
    expect(evaluationApi.submitEvaluation).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", { name: "Run ITSO Evaluation" }),
    );
    await waitFor(() => expect(onSubmitted).toHaveBeenCalledWith("eval-1"));
    expect(evaluationApi.submitEvaluation).toHaveBeenCalledTimes(1);
    expect(evaluationApi.submitEvaluation).toHaveBeenCalledWith({
      document_id: "doc-1",
      target_agent: "itso",
      confirmed_program: "BSCS",
      partial_without_curriculum: false,
    });
    expect(documentsApi.getCurriculumSuggestion).not.toHaveBeenCalled();
  });

  it("requires verified curriculum and explicit confirmation before submitting the existing payload", async () => {
    const { onSubmitted } = renderSetup();
    expect(
      (
        screen.getByRole("button", {
          name: "Start evaluation",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    await selectCurriculum();
    fireEvent.click(screen.getByRole("button", { name: "Start evaluation" }));
    const dialog = screen.getByRole("dialog", {
      name: "Start Coordinator evaluation?",
    });
    expect(
      within(dialog).getByText(/BSCS.*Verified curriculum 2026/),
    ).toBeDefined();
    expect(evaluationApi.submitEvaluation).not.toHaveBeenCalled();
    fireEvent.click(
      within(dialog).getByRole("button", {
        name: "Run Coordinator Evaluation",
      }),
    );
    await waitFor(() => expect(onSubmitted).toHaveBeenCalledWith("eval-1"));
    expect(evaluationApi.submitEvaluation).toHaveBeenCalledTimes(1);
    expect(evaluationApi.submitEvaluation).toHaveBeenCalledWith({
      document_id: "doc-1",
      target_agent: "coordinator",
      curriculum_id: "curr-1",
      confirmed_program: "BSCS",
      partial_without_curriculum: false,
    });
  });

  it.each(["verification_disabled"])(
    "explains missing ITSO search configuration without submitting an offline run: %s",
    async (code) => {
      vi.mocked(evaluationApi.submitEvaluation).mockRejectedValue(
        new Error(code),
      );
      const { onSubmitted } = renderSetup("itso");
      fireEvent.click(screen.getByRole("button", { name: "Start evaluation" }));
      fireEvent.click(
        screen.getByRole("button", { name: "Run ITSO Evaluation" }),
      );
      await waitFor(() =>
        expect(screen.getByRole("alert").textContent).toContain("server"),
      );
      expect(screen.getByRole("alert").textContent).not.toContain(
        "administrator",
      );
      expect(screen.getByRole("alert").textContent).not.toContain(code);
      expect(onSubmitted).not.toHaveBeenCalled();
      expect(screen.queryByRole("checkbox")).toBeNull();
    },
  );

  it("clears the selected reference when the confirmed program changes", async () => {
    renderSetup();
    await selectCurriculum();
    fireEvent.click(screen.getByRole("button", { name: "Confirmed program" }));
    fireEvent.click(
      screen.getByRole("option", {
        name: "BSInfoTech · Information Technology",
      }),
    );
    await waitFor(() =>
      expect(documentsApi.getCurriculumSuggestion).toHaveBeenLastCalledWith(
        "doc-1",
        "BSInfoTech",
      ),
    );
    expect(
      (
        screen.getByRole("button", {
          name: "Start evaluation",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    expect(evaluationApi.submitEvaluation).not.toHaveBeenCalled();
  });

  it("keeps failed admission in setup with the server error and without starting progress", async () => {
    vi.mocked(evaluationApi.submitEvaluation).mockRejectedValue(
      new Error("Evaluation capacity is full."),
    );
    const { onSubmitted } = renderSetup("sme");
    fireEvent.click(screen.getByRole("button", { name: "Start evaluation" }));
    fireEvent.click(screen.getByRole("button", { name: "Run SME Evaluation" }));
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain(
        "Evaluation capacity is full.",
      ),
    );
    expect(
      screen.getByRole("dialog", { name: "Start SME evaluation?" }),
    ).toBeDefined();
    expect(
      screen.getByRole("heading", { name: "Prepare the review" }),
    ).toBeDefined();
    expect(onSubmitted).not.toHaveBeenCalled();
    expect(documentsApi.getCurriculumSuggestion).not.toHaveBeenCalled();
  });
});
