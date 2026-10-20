// @vitest-environment jsdom
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { EvaluationResultsResponse } from "../../types";
import { ScorecardPdfExport } from "../ScorecardPdfExport";

const exportPdf = vi.hoisted(() => vi.fn());
vi.mock("../../utils/scorecardPdf", () => ({ exportScorecardPdf: exportPdf }));
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  exportPdf.mockReset();
});

const results: EvaluationResultsResponse = {
  evaluation_id: "saved-evaluation",
  document_id: "module",
  synthesized_score: null,
  domain_scores: {},
  flags: [],
  active_agents: [],
  failed_agents: [],
  is_partial: false,
  evaluation_status: "COMPLETED",
};

describe("scorecard PDF control", () => {
  it("uses the saved result and prevents duplicate export while rendering", async () => {
    let finish!: () => void;
    exportPdf.mockReturnValue(
      new Promise<void>((resolve) => {
        finish = resolve;
      }),
    );
    render(<ScorecardPdfExport results={results} />);
    fireEvent.click(
      screen.getByRole("button", { name: "Export Scorecard PDF" }),
    );
    expect(exportPdf).toHaveBeenCalledWith(results);
    expect(
      (
        screen.getByRole("button", {
          name: "Creating PDF...",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Creating PDF..." }));
    expect(exportPdf).toHaveBeenCalledTimes(1);
    await act(async () => {
      finish();
    });
    expect(
      (
        screen.getByRole("button", {
          name: "Export Scorecard PDF",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(false);
  });

  it("announces an export failure and clears the error on retry", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    exportPdf
      .mockRejectedValueOnce(new Error("renderer unavailable"))
      .mockResolvedValueOnce(undefined);
    render(<ScorecardPdfExport results={results} />);
    fireEvent.click(
      screen.getByRole("button", { name: "Export Scorecard PDF" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toBe(
        "PDF export failed. Please try again.",
      ),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Export Scorecard PDF" }),
    );
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    expect(exportPdf).toHaveBeenCalledTimes(2);
  });
});
