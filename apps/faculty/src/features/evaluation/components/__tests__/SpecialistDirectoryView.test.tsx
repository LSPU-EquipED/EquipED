// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SpecialistDirectoryView } from "../SpecialistDirectoryView";

vi.mock("@tanstack/react-router", () => ({ useNavigate: () => vi.fn() }));
afterEach(cleanup);

describe("SpecialistDirectoryView module browser", () => {
  it.each(["READY", "COMPLETED"])(
    "keeps a single selector for a %s module",
    (status) => {
      render(
        <SpecialistDirectoryView
          validAgent="sme"
          items={[
            {
              document_id: "completed-module",
              title: "Previously evaluated SLM",
              course_code: "CS101",
              program: "BSCS",
              uploaded_at: "2026-10-15T00:00:00Z",
              my_status: status,
              my_score: 3,
              my_adjectival: "Satisfactory",
              peer_completed_count: 1,
              peer_completed_desks: ["sme"],
            },
          ]}
        />,
      );
      expect(
        screen.queryByRole("button", { name: "Browse modules" }),
      ).toBeNull();
      expect(
        screen.getAllByRole("button", { name: "Select module" }),
      ).toHaveLength(1);
      fireEvent.click(screen.getByRole("button", { name: "Select module" }));
      expect(
        screen.getByRole("dialog", { name: "Select module" }),
      ).toBeDefined();
      expect(
        screen.getByRole("button", {
          name: new RegExp(
            `Previously evaluated SLM.*${status === "COMPLETED" ? "View results" : "Evaluate"}`,
          ),
        }),
      ).toBeDefined();
    },
  );
  it("keeps every active review accessible when more than three modules are running", () => {
    const statuses = [
      "READY",
      "SUBMITTED",
      "PREPROCESSING",
      "EVALUATING",
      "SYNTHESIZING",
      "COMPLETED",
    ];
    render(
      <SpecialistDirectoryView
        validAgent="sme"
        items={statuses.map((status, index) => ({
          document_id: `module-${index}`,
          title: `Module ${index}`,
          course_code: "CS101",
          program: "BSCS",
          uploaded_at: "2026-10-15T00:00:00Z",
          my_status: status,
          my_score: null,
          my_adjectival: null,
          peer_completed_count: 0,
          peer_completed_desks: [],
        }))}
      />,
    );
    expect(
      screen.getAllByRole("button", { name: /^View progress Module/ }),
    ).toHaveLength(4);
    expect(screen.getByText("4 evaluations in progress")).toBeDefined();
    expect(
      screen.queryByRole("button", { name: "Evaluate Module 0" }),
    ).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Select module" }));
    const selector = screen.getByRole("dialog", { name: "Select module" });
    expect(
      within(selector).getByRole("button", { name: /Module 0.*Evaluate/ }),
    ).toBeDefined();
    expect(
      within(selector).getByRole("button", { name: /Module 5.*View results/ }),
    ).toBeDefined();
  });
});
