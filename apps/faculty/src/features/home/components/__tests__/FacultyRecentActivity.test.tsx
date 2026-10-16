import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { ReactNode } from "react";
import { FacultyRecentActivity } from "../FacultyRecentActivity";
import type { HomeEvaluationItem } from "../../types";

vi.mock("@tanstack/react-router", () => ({
  Link: ({
    to,
    params,
    children,
  }: {
    to: string;
    params?: Record<string, string>;
    children?: ReactNode;
  }) => (
    <a
      href={Object.entries(params ?? {}).reduce(
        (path, [key, value]) => path.replace(`$${key}`, value),
        to,
      )}
    >
      {children}
    </a>
  ),
}));

const evaluation = (
  id: string,
  status: string,
  date: string,
): HomeEvaluationItem => ({
  evaluation_id: id,
  document_id: "doc-1",
  document_title: "Human–Computer Interaction",
  target_agent: "coordinator",
  syllabus_id: "",
  curriculum_id: "",
  status,
  submitted_at: date,
});

describe("FacultyRecentActivity", () => {
  it("shows the newest three runs without treating older failures as outstanding work", () => {
    const evaluations = [
      evaluation("old", "COMPLETED", "2026-10-12T12:00:00Z"),
      evaluation("failed", "FAILED", "2026-10-15T12:00:00Z"),
      evaluation("complete", "COMPLETED", "2026-10-16T12:00:00Z"),
      evaluation("partial", "COMPLETED_PARTIAL", "2026-10-14T12:00:00Z"),
    ];
    const markup = renderToStaticMarkup(
      <FacultyRecentActivity evaluations={evaluations} isLoading={false} />,
    );
    expect(markup).not.toContain('href="/evaluations/old"');
    expect(markup.indexOf("/evaluations/complete")).toBeLessThan(
      markup.indexOf("/evaluations/failed"),
    );
    expect(markup).toContain("Failed");
    expect(markup).toContain("Completed (Partial)");
    expect(markup).toContain("Coordinator");
    expect(markup).not.toContain("Requires review");
    expect(evaluations[0].evaluation_id).toBe("old");
  });

  it("does not assign a specialist identity to legacy combined results", () => {
    const combined = {
      ...evaluation("combined", "COMPLETED", "2026-10-16T12:00:00Z"),
      target_agent: "all",
    };
    const markup = renderToStaticMarkup(
      <FacultyRecentActivity evaluations={[combined]} isLoading={false} />,
    );
    expect(markup).toContain('href="/evaluations/combined"');
    expect(markup).toContain(">Evaluation</span>");
    expect(markup).not.toContain("Coordinator");
  });
});
