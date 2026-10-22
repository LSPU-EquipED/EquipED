// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ComponentProps } from "react";
import type { ClientDocument } from "@equiped/types";
import { AlignmentCheckControls } from "../AlignmentCheckControls";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ to, children, ...props }: ComponentProps<"a"> & { to: string }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));

const moduleItem: ClientDocument = {
  documentId: "doc-1",
  title: "Networking module",
  sourceType: "slm",
  processingStatus: "PROCESSED",
  program: "BSInfoTech",
  courseTitle: null,
  lessonTitle: null,
  academicYear: null,
  courseCode: null,
  pageCount: null,
  hasOcrPages: false,
  uploadedAt: "2026-10-01T00:00:00Z",
  chunks: [],
};

function props(
  overrides: Partial<ComponentProps<typeof AlignmentCheckControls>> = {},
): ComponentProps<typeof AlignmentCheckControls> {
  return {
    documentId: "",
    courseId: "",
    pickerDocuments: [moduleItem],
    selectedDocument: null,
    selectedEligibility: { eligible: false, message: null },
    courseOptions: [{ value: "course-1", label: "IT101 — Networking" }],
    documentsLoading: false,
    coursesLoading: false,
    documentsError: null,
    coursesError: null,
    canRunCheck: false,
    isPending: false,
    onDocumentChange: vi.fn(),
    onCourseChange: vi.fn(),
    onRetryDocuments: vi.fn(),
    onRetryCourses: vi.fn(),
    onRun: vi.fn(),
    ...overrides,
  };
}
afterEach(cleanup);

describe("AlignmentCheckControls", () => {
  it("uses the shared dropdowns to select a module and course", () => {
    const input = props();
    render(<AlignmentCheckControls {...input} />);
    fireEvent.click(screen.getByRole("button", { name: "Module" }));
    fireEvent.click(screen.getByRole("option", { name: "Networking module" }));
    expect(input.onDocumentChange).toHaveBeenCalledWith("doc-1");
    fireEvent.click(screen.getByRole("button", { name: "Target course" }));
    fireEvent.click(screen.getByRole("option", { name: "IT101 — Networking" }));
    expect(input.onCourseChange).toHaveBeenCalledWith("course-1");
    expect(
      (screen.getByRole("button", { name: "Run check" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    expect(input.onRun).not.toHaveBeenCalled();
  });

  it("runs only when the supplied selection is eligible", () => {
    const input = props({
      documentId: "doc-1",
      courseId: "course-1",
      selectedDocument: moduleItem,
      selectedEligibility: { eligible: true, message: null },
      canRunCheck: true,
    });
    render(<AlignmentCheckControls {...input} />);
    fireEvent.click(screen.getByRole("button", { name: "Run check" }));
    expect(input.onRun).toHaveBeenCalledOnce();
  });

  it("locks selectors and repeat submissions while checking", () => {
    const input = props({ isPending: true, canRunCheck: true });
    render(<AlignmentCheckControls {...input} />);
    for (const name of ["Module", "Target course", "Checking…"]) {
      expect(
        (screen.getByRole("button", { name }) as HTMLButtonElement).disabled,
      ).toBe(true);
    }
    fireEvent.click(screen.getByRole("button", { name: "Checking…" }));
    expect(input.onRun).not.toHaveBeenCalled();
  });

  it("explains an empty eligible picker and links to owned module storage", () => {
    render(<AlignmentCheckControls {...props({ pickerDocuments: [] })} />);
    expect(
      screen.getByText("No processed BSCS or BSInfoTech SLMs available."),
    ).toBeDefined();
    expect(
      (screen.getByRole("button", { name: "Module" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    expect(
      screen
        .getByRole("link", { name: "Open Module library" })
        .getAttribute("href"),
    ).toBe("/documents");
  });

  it("distinguishes loading and failed requests from empty data", () => {
    const input = props({
      documentsLoading: true,
      coursesLoading: true,
      pickerDocuments: [],
      courseOptions: [],
    });
    const view = render(<AlignmentCheckControls {...input} />);
    expect(screen.getByText("Loading modules…")).toBeDefined();
    expect(
      screen.queryByText("No processed BSCS or BSInfoTech SLMs available."),
    ).toBeNull();
    view.rerender(
      <AlignmentCheckControls
        {...input}
        documentsLoading={false}
        coursesLoading={false}
        documentsError="Modules request failed"
        coursesError="Courses request failed"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry modules" }));
    fireEvent.click(screen.getByRole("button", { name: "Retry courses" }));
    expect(input.onRetryDocuments).toHaveBeenCalledOnce();
    expect(input.onRetryCourses).toHaveBeenCalledOnce();
    expect(
      screen.queryByRole("link", { name: "Open Module library" }),
    ).toBeNull();
  });

  it("keeps an ineligible historical selection visible without allowing a new run", () => {
    render(
      <AlignmentCheckControls
        {...props({
          documentId: "legacy",
          selectedDocument: {
            ...moduleItem,
            documentId: "legacy",
            title: "Legacy module",
          },
          selectedEligibility: {
            eligible: false,
            message: "Not eligible for alignment checks.",
          },
        })}
      />,
    );
    expect(
      screen.getByText("Not eligible for alignment checks."),
    ).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Module" }));
    expect(
      screen
        .getByRole("option", { name: "Legacy module" })
        .getAttribute("aria-disabled"),
    ).toBe("true");
    expect(
      (screen.getByRole("button", { name: "Run check" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
  });
});
