// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  WorkspaceLoading,
  WorkspaceRecovery,
} from "../workspace/WorkspaceStates";

afterEach(cleanup);

describe("specialist workspace loading and recovery", () => {
  it("announces loading without exposing counts or evaluation actions", () => {
    render(<WorkspaceLoading />);
    expect(
      screen
        .getByRole("status", { name: "Loading specialist workspace" })
        .getAttribute("aria-busy"),
    ).toBe("true");
    expect(screen.queryByLabelText("Workspace summary")).toBeNull();
    expect(screen.queryByRole("button", { name: "Select module" })).toBeNull();
  });

  it("allows retrying a workspace retrieval error", () => {
    const retry = vi.fn();
    render(<WorkspaceRecovery kind="workspace" onRetry={retry} />);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: "Review scores" })).toBeNull();
  });

  it("reveals failure details independently of the recovery action", () => {
    const retry = vi.fn();
    render(
      <WorkspaceRecovery
        kind="evaluation"
        errorMessage="The review was interrupted."
        onRetry={retry}
      />,
    );
    const toggle = screen.getByRole("button", { name: "Failure details" });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(
      screen.queryByRole("region", { name: "Failure details" }),
    ).toBeNull();
    fireEvent.click(toggle);
    const details = screen.getByRole("region", { name: "Failure details" });
    expect(toggle.getAttribute("aria-controls")).toBe(details.id);
    expect(details.textContent).toContain("The review was interrupted.");
    fireEvent.click(toggle);
    expect(
      screen.queryByRole("region", { name: "Failure details" }),
    ).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Review setup" }));
    expect(retry).toHaveBeenCalledTimes(1);
  });
});
