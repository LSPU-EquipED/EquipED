// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { ObjectiveForm } from "../components/ObjectiveForm";

const mutation = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  isPending: false,
  error: null as Error | null,
}));
vi.mock("../hooks", () => ({
  useSaveObjective: () => mutation,
  useUnsavedChanges: vi.fn(),
}));
beforeEach(() => {
  mutation.mutateAsync.mockReset().mockResolvedValue({});
  mutation.error = null;
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ObjectiveForm", () => {
  it("reloads stale data only after confirming discard of entered changes", async () => {
    mutation.error = new Error(
      "This objective changed. Reload it before saving.",
    );
    const reload = vi.fn().mockResolvedValue(undefined);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(
      <ObjectiveForm
        objective={{
          objective_id: "id",
          code: "IT13",
          description: "Existing",
          program: "BSInfoTech",
          version: 1,
          mapping_count: 0,
        }}
        onClose={vi.fn()}
        onReload={reload}
      />,
    );
    fireEvent.change(screen.getByRole("textbox", { name: /Description/ }), {
      target: { value: "Unsaved text" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Reload latest objective" }),
    );
    expect(reload).not.toHaveBeenCalled();
    expect(screen.getByDisplayValue("Unsaved text")).toBeDefined();
    confirm.mockReturnValue(true);
    fireEvent.click(
      screen.getByRole("button", { name: "Reload latest objective" }),
    );
    await waitFor(() => expect(reload).toHaveBeenCalledOnce());
  });
  it("requires a program and offers only the two approved choices", async () => {
    const close = vi.fn();
    render(<ObjectiveForm onClose={close} />);
    fireEvent.change(screen.getByRole("textbox", { name: /Code/ }), {
      target: { value: " it13 " },
    });
    fireEvent.change(screen.getByRole("textbox", { name: /Description/ }), {
      target: { value: "New objective" },
    });
    fireEvent.submit(
      screen.getByRole("button", { name: "Save objective" }).closest("form")!,
    );
    expect(screen.getByRole("alert").textContent).toContain(
      "program are required",
    );
    expect(mutation.mutateAsync).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /Program/ }));
    expect(
      screen.getAllByRole("option").map((option) => option.textContent),
    ).toEqual(["BSCS", "BSInfoTech"]);
    fireEvent.click(screen.getByRole("option", { name: "BSInfoTech" }));
    fireEvent.submit(
      screen.getByRole("button", { name: "Save objective" }).closest("form")!,
    );
    await waitFor(() => expect(close).toHaveBeenCalledOnce());
    expect(mutation.mutateAsync).toHaveBeenCalledWith({
      code: "IT13",
      description: "New objective",
      program: "BSInfoTech",
    });
  });

  it("preselects the saved program and sends the edit version", async () => {
    render(
      <ObjectiveForm
        objective={{
          objective_id: "id",
          code: "CS01",
          description: "Existing",
          program: "BSCS",
          version: 3,
          mapping_count: 2,
        }}
        onClose={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: /Program/ }).textContent,
    ).toContain("BSCS");
    expect(screen.queryByDisplayValue("id")).toBeNull();
    fireEvent.change(screen.getByRole("textbox", { name: /Description/ }), {
      target: { value: "Updated" },
    });
    fireEvent.submit(
      screen.getByRole("button", { name: "Save objective" }).closest("form")!,
    );
    await waitFor(() =>
      expect(mutation.mutateAsync).toHaveBeenCalledWith({
        code: "CS01",
        description: "Updated",
        program: "BSCS",
        version: 3,
      }),
    );
  });

  it("keeps entered values when a stale save fails", async () => {
    mutation.error = new Error(
      "This objective changed. Reload it before saving.",
    );
    mutation.mutateAsync.mockRejectedValue(mutation.error);
    const close = vi.fn();
    render(
      <ObjectiveForm
        objective={{
          objective_id: "id",
          code: "IT13",
          description: "Existing",
          program: "BSInfoTech",
          version: 1,
          mapping_count: 0,
        }}
        onClose={close}
      />,
    );
    fireEvent.change(screen.getByRole("textbox", { name: /Description/ }), {
      target: { value: "Keep my text" },
    });
    fireEvent.submit(
      screen.getByRole("button", { name: "Save objective" }).closest("form")!,
    );
    await waitFor(() => expect(mutation.mutateAsync).toHaveBeenCalled());
    expect(screen.getByRole("alert").textContent).toContain("Reload");
    expect(screen.getByDisplayValue("Keep my text")).toBeDefined();
    expect(close).not.toHaveBeenCalled();
  });
});
