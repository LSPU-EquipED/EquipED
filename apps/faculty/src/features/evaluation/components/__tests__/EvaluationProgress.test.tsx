// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { TargetAgent } from "@equiped/types";
import { EvaluationProgress } from "../EvaluationProgress";

afterEach(cleanup);

describe("EvaluationProgress", () => {
  it.each([
    ["SUBMITTED", "Queued", "Your evaluation is queued", 0],
    ["PREPROCESSING", "Preparation", "Preparing your learning material", 1],
    ["EVALUATING", "Specialist review", "Reviewing your learning material", 2],
    ["SYNTHESIZING", "Finalizing", "Finalizing your evaluation", 3],
  ])(
    "shows only the server-reported %s stage",
    (status, label, heading, doneCount) => {
      render(
        <EvaluationProgress
          targetAgent="sme"
          status={status}
          documentTitle="Algorithms SLM"
        />,
      );

      const stages = screen.getByRole("list", { name: "Evaluation stages" });
      expect(
        within(stages)
          .getByText(label)
          .closest("li")
          ?.getAttribute("aria-current"),
      ).toBe("step");
      expect(within(stages).queryAllByText(", done")).toHaveLength(doneCount);
      expect(screen.getByRole("status").textContent).toContain(heading);
      expect(
        screen.getByRole("region", {
          name: "Evaluation progress for Algorithms SLM",
        }),
      ).toBeDefined();
      expect(screen.queryByRole("progressbar")).toBeNull();
      expect(screen.queryByText(/seconds|percent|%/)).toBeNull();
    },
  );

  it.each<[TargetAgent, string, string]>([
    ["sme", "SME", "content accuracy and instructional quality"],
    ["coordinator", "Coordinator", "curriculum alignment"],
    ["gad", "GAD", "inclusivity and gender responsiveness"],
    [
      "itso",
      "ITSO",
      "intellectual property, citation practice, and data privacy",
    ],
  ])("identifies only the selected %s specialist", (agent, label, focus) => {
    render(<EvaluationProgress targetAgent={agent} status="EVALUATING" />);
    expect(
      screen.getByRole("figure", {
        name: `Module → ${label} specialist → Findings`,
      }),
    ).toBeDefined();
    expect(screen.getByRole("status").textContent).toContain(focus);
    expect(screen.queryByText("Specialist team")).toBeNull();
  });

  it("keeps historical bundle progress distinct from a single specialist run", () => {
    render(<EvaluationProgress targetAgent="all" status="EVALUATING" />);
    expect(screen.getByText("Specialist team")).toBeDefined();
    expect(screen.queryByText("SME specialist")).toBeNull();
  });

  it("does not invent a stage before the job status is available", () => {
    render(<EvaluationProgress targetAgent="sme" />);
    expect(screen.getByRole("status").textContent).toContain(
      "Waiting for the latest evaluation stage",
    );
    expect(screen.queryByText(", in progress")).toBeNull();
    expect(screen.queryByText(", done")).toBeNull();
  });
});
