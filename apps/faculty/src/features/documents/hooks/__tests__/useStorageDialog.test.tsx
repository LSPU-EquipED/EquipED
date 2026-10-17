// @vitest-environment jsdom
import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Dropdown } from "@equiped/ui";
import { useStorageDialog } from "../useStorageDialog";

function DialogExample({ pending = false }: { pending?: boolean }) {
  const [open, setOpen] = useState(false);
  const ref = useStorageDialog({
    isOpen: open,
    isMounted: open,
    onClose: () => setOpen(false),
    preventClose: pending,
  });
  return (
    <>
      <button onClick={() => setOpen(true)}>Open dialog</button>
      {open && (
        <div ref={ref} role="dialog" tabIndex={-1}>
          <button onClick={() => setOpen(false)}>Close</button>
          <Dropdown
            aria-label="Program"
            options={[{ value: "BSCS", label: "BSCS" }]}
          />
          <button>Last action</button>
        </div>
      )}
    </>
  );
}
afterEach(() => {
  cleanup();
  document.body.style.overflow = "";
});

describe("useStorageDialog", () => {
  it("moves and traps focus, makes the background inert, and restores it on close", () => {
    render(<DialogExample />);
    const trigger = screen.getByRole("button", { name: "Open dialog" });
    trigger.focus();
    fireEvent.click(trigger);
    const first = screen.getByRole("button", { name: "Close" });
    const last = screen.getByRole("button", { name: "Last action" });
    expect(document.activeElement).toBe(first);
    expect(trigger.hasAttribute("inert")).toBe(true);
    expect(document.body.style.overflow).toBe("hidden");
    fireEvent.keyDown(first, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);
    fireEvent.keyDown(last, { key: "Tab" });
    expect(document.activeElement).toBe(first);
    fireEvent.click(first);
    expect(trigger.hasAttribute("inert")).toBe(false);
    expect(document.activeElement).toBe(trigger);
    expect(document.body.style.overflow).toBe("");
  });
  it("closes a dropdown on Escape before dismissing its containing dialog", () => {
    render(<DialogExample />);
    fireEvent.click(screen.getByRole("button", { name: "Open dialog" }));
    fireEvent.click(screen.getByRole("button", { name: "Program" }));
    fireEvent.keyDown(screen.getByRole("listbox"), { key: "Escape" });
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(screen.getByRole("dialog")).toBeDefined();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });
  it("keeps a pending operation open on Escape", () => {
    render(<DialogExample pending />);
    fireEvent.click(screen.getByRole("button", { name: "Open dialog" }));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.getByRole("dialog")).toBeDefined();
  });
});
