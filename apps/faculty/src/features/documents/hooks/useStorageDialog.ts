import { useEffect, useRef } from "react";

const FOCUSABLE =
  'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [tabindex]:not([tabindex="-1"])';

/** Keeps storage overlays modal through keyboard focus, background inertness, and scroll locking. */
export function useStorageDialog({
  isOpen,
  isMounted,
  onClose,
  preventClose = false,
}: {
  isOpen: boolean;
  isMounted: boolean;
  onClose: () => void;
  preventClose?: boolean;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const handlers = useRef({ onClose, preventClose });
  useEffect(() => {
    handlers.current = { onClose, preventClose };
  }, [onClose, preventClose]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!isMounted || !dialog) return;
    if (!isOpen) {
      dialog.setAttribute("inert", "");
      return () => dialog.removeAttribute("inert");
    }
    const previous =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const previousOverflow = document.body.style.overflow;
    const siblings: { element: HTMLElement; inert: boolean }[] = [];
    let branch: HTMLElement = dialog;
    while (branch.parentElement) {
      for (const sibling of branch.parentElement.children) {
        if (sibling !== branch && sibling instanceof HTMLElement) {
          siblings.push({
            element: sibling,
            inert: sibling.hasAttribute("inert"),
          });
          sibling.setAttribute("inert", "");
        }
      }
      branch = branch.parentElement;
    }
    document.body.style.overflow = "hidden";
    const focusable = () =>
      Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (element) =>
          !element.closest('[inert], [hidden], [aria-hidden="true"]') &&
          (!element.closest("details:not([open])") ||
            element.tagName === "SUMMARY") &&
          element.tabIndex !== -1,
      );
    const focusStart = () =>
      (focusable()[0] ?? dialog).focus({ preventScroll: true });
    focusStart();
    const keydown = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (event.key === "Escape") {
        if (
          event.target instanceof Element &&
          event.target.closest('[role="listbox"], [role="menu"]')
        )
          return;
        if (!handlers.current.preventClose) handlers.current.onClose();
      }
      if (event.key === "Tab") {
        const items = focusable();
        const first = items[0];
        const last = items[items.length - 1];
        if (!first) {
          event.preventDefault();
          dialog.focus();
        } else if (
          event.shiftKey &&
          (document.activeElement === first ||
            document.activeElement === dialog)
        ) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    const focusin = (event: FocusEvent) => {
      if (event.target instanceof Node && !dialog.contains(event.target))
        focusStart();
    };
    window.addEventListener("keydown", keydown);
    document.addEventListener("focusin", focusin);
    return () => {
      window.removeEventListener("keydown", keydown);
      document.removeEventListener("focusin", focusin);
      siblings.forEach(({ element, inert }) => {
        if (!inert) element.removeAttribute("inert");
      });
      document.body.style.overflow = previousOverflow;
      if (previous?.isConnected) previous.focus();
    };
  }, [isOpen, isMounted]);
  return dialogRef;
}
