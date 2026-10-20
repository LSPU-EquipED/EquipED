import { afterEach, expect, it, vi } from "vitest";
import { PDFDocument } from "pdf-lib";
import type { EvaluationResultsResponse } from "../../types";
import { exportScorecardPdf } from "../scorecardPdf";

const downloads = vi.hoisted(
  () => [] as { filename: string; bytes: ArrayBuffer }[],
);
vi.mock("jspdf", async (importOriginal) => {
  const actual = await importOriginal<typeof import("jspdf")>();
  return {
    ...actual,
    jsPDF: new Proxy(actual.jsPDF, {
      construct(target, args) {
        const pdf = Reflect.construct(target, args) as InstanceType<
          typeof actual.jsPDF
        >;
        vi.spyOn(pdf, "save").mockImplementation((filename = "document.pdf") => {
          downloads.push({ filename, bytes: pdf.output("arraybuffer") });
          return pdf;
        });
        return pdf;
      },
    }),
  };
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  downloads.length = 0;
});

it("exports the actual saved-result report when optional logo and Unicode assets are unavailable", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response("", { status: 404 })),
  );
  const results: EvaluationResultsResponse = {
    evaluation_id: "saved-evaluation",
    document_id: "module",
    document_title: "Module review",
    program: "BSCS",
    overall_score: 3,
    synthesized_score: 75,
    evaluation_status: "COMPLETED",
    domain_scores: {
      itso: {
        subtotal: 3,
        max_score: 4,
        status: "OK",
        form_snapshot_id: "saved-form",
        version: 3,
        criteria: [
          {
            criterion_id: "ITSO-01",
            criterion_text: "Source comparison",
            score: 3,
            justification: "A scoped advisory finding.",
          },
        ],
      },
    },
    flags: [],
    active_agents: ["itso"],
    failed_agents: [],
    is_partial: false,
  };
  await exportScorecardPdf(results);
  expect(downloads).toHaveLength(1);
  expect(downloads[0].filename).toBe("EquipED-scorecard-saved-evaluation.pdf");
  const pdf = await PDFDocument.load(downloads[0].bytes);
  expect(pdf.getPageCount()).toBeGreaterThan(0);
  expect(pdf.getPage(0).getWidth()).toBeCloseTo(595.28, 1);
});
