// @vitest-environment jsdom
import { assessmentFixture } from "../../../../../../../libs/types/src/__tests__/itso.fixture";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SpecialistScoreboardPage } from "../SpecialistScoreboardPage";
import { Scorecard } from "../../components/Scorecard";

const navigate = vi.hoisted(() => vi.fn());
vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => navigate,
  useParams: () => ({
    id: "evaluation-1",
    agentId: "itso",
    documentId: "document-1",
  }),
  Link: ({ children }: { children: React.ReactNode }) => (
    <a href="/specialists/itso">{children}</a>
  ),
}));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
describe("mounted specialist ITSO vertical", () => {
  it.each([
    ["COMPLETED", "workspace"],
    ["FAILED", "workspace"],
    ["COMPLETED", "history"],
    ["FAILED", "history"],
  ] as const)(
    "reads %s ITSO findings from %s and starts a new evidence review without a version choice",
    async (status, entry) => {
      let submitted = false;
      const document = {
        document_id: "document-1",
        title: "Synthetic owned module",
        source_type: "slm",
        program: "BSCS",
        processing_status: "PROCESSED",
        course_title: null,
        lesson_title: null,
        academic_year: null,
        course_code: "CS101",
        page_count: 2,
        has_ocr_pages: false,
        uploaded_at: "2026-10-20T00:00:00Z",
      };
      const oldJob = {
        evaluation_id: "evaluation-1",
        document_id: "document-1",
        target_agent: "itso",
        status,
        submitted_at: "2026-10-20T00:00:00Z",
        completed_at: "2026-10-20T00:01:00Z",
        error_message: null,
        confirmed_program: "BSCS",
        syllabus_id: null,
        curriculum_id: null,
        duration_seconds: 60,
      };
      const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
        if (url.includes("/documents?"))
          return json({ items: [document], total: 1, page: 1, page_size: 100 });
        if (url.endsWith("/documents/document-1")) return json(document);
        if (url.includes("/desk-queue?"))
          return json({
            items: [
              {
                document_id: "document-1",
                title: document.title,
                course_code: "CS101",
                program: "BSCS",
                uploaded_at: document.uploaded_at,
                my_status: submitted ? "EVALUATING" : "COMPLETED",
                my_score: null,
                my_adjectival: null,
                peer_completed_count: 0,
                peer_completed_desks: [],
              },
            ],
            total: 1,
          });
        if (url.endsWith("/evaluations/") && init?.method === "POST") {
          submitted = true;
          return json(
            {
              ...oldJob,
              evaluation_id: "new-run",
              status: "SUBMITTED",
              completed_at: null,
            },
            202,
          );
        }
        if (url.includes("/evaluations/?"))
          return json({
            items: submitted
              ? [
                  {
                    ...oldJob,
                    evaluation_id: "new-run",
                    status: "SUBMITTED",
                    completed_at: null,
                  },
                  oldJob,
                ]
              : [oldJob],
            total: submitted ? 2 : 1,
            page: 1,
            page_size: 100,
          });
        if (url.endsWith("/evaluations/evaluation-1/assessment")) {
          const assessment = assessmentFixture();
          assessment.execution_status = status;
          assessment.error_code =
            status === "FAILED" ? "model_schema_failure" : null;
          return json(assessment);
        }
        if (url.endsWith("/evaluations/evaluation-1")) return json(oldJob);
        throw new Error(`Unexpected synthetic route ${url}`);
      });
      vi.stubGlobal("fetch", fetcher);
      const client = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });
      render(
        <QueryClientProvider client={client}>
          {entry === "history" ? (
            <Scorecard />
          ) : (
            <SpecialistScoreboardPage agentId="itso" documentId="document-1" />
          )}
        </QueryClientProvider>,
      );
      await screen.findByText(
        status === "FAILED"
          ? /Evaluation failed. Available findings are diagnostic only/
          : "Archived observations with their available source evidence. These observations were not confirmed compliance findings.",
      );
      expect(
        globalThis.document.querySelectorAll(
          'details[class~="group/criterion"]',
        ),
      ).toHaveLength(5);
      expect(fetcher.mock.calls.some(([url]) => url.endsWith("/results"))).toBe(
        false,
      );
      fireEvent.click(screen.getByRole("button", { name: "Re-evaluate" }));
      expect(
        screen.queryByRole("button", { name: "ITSO assessment version" }),
      ).toBeNull();
      expect(
        screen.queryByText("Prepare source and read local inventory"),
      ).toBeNull();
      expect(screen.queryByLabelText(/I confirm this exact source/)).toBeNull();
      expect(screen.getByText(/This creates a new run/)).toBeTruthy();
      fireEvent.click(
        screen.getByRole("button", { name: "Run ITSO Evaluation" }),
      );
      await waitFor(() => expect(submitted).toBe(true));
      const posts = fetcher.mock.calls.filter(
        ([url, init]) =>
          url.endsWith("/evaluations/") && init?.method === "POST",
      );
      expect(posts).toHaveLength(1);
      expect(JSON.parse(String(posts[0][1]?.body))).toEqual({
        document_id: "document-1",
        target_agent: "itso",
        confirmed_program: "BSCS",
        partial_without_curriculum: false,
      });
      expect(JSON.stringify(client.getMutationCache().getAll())).not.toContain(
        "synthetic-one-use-nonce",
      );
      expect(
        JSON.stringify(
          client
            .getQueryCache()
            .getAll()
            .map((q) => q.state.data),
        ),
      ).not.toContain("synthetic-one-use-nonce");
      await waitFor(() => expect(navigate).toHaveBeenCalled());
      client.clear();
    },
  );
});
