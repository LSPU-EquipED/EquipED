// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StorageToolbar } from "../StorageToolbar";
afterEach(cleanup);

describe("StorageToolbar", () => {
  it("filters programs and file processing through shared dropdowns without unstable counts", () => {
    const program = vi.fn();
    const status = vi.fn();
    render(
      <StorageToolbar
        programFilter="ALL"
        setProgramFilter={program}
        statusFilter="all"
        setStatusFilter={status}
      />,
    );
    expect(screen.queryByRole("tablist")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Program" }));
    fireEvent.click(screen.getByRole("option", { name: "BSInfoTech" }));
    expect(program).toHaveBeenCalledWith("BSInfoTech");
    fireEvent.click(screen.getByRole("button", { name: "File status" }));
    fireEvent.click(screen.getByRole("option", { name: "Upload failed" }));
    expect(status).toHaveBeenCalledWith("FAILED");
  });
  it("requests whole-inventory sorting through its parent handler", () => {
    const sort = vi.fn();
    render(
      <StorageToolbar
        programFilter="ALL"
        setProgramFilter={vi.fn()}
        statusFilter="all"
        setStatusFilter={vi.fn()}
        sortOption="uploaded-desc"
        setSortOption={sort}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Sort" }));
    fireEvent.click(screen.getByRole("option", { name: "Oldest first" }));
    expect(sort).toHaveBeenCalledWith("uploaded-asc");
  });
});
