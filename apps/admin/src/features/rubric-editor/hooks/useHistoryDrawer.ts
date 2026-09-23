import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';

function getFocusableElements(container: HTMLElement): HTMLElement[] {
  const selector = [
    'a[href]',
    'button:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"]):not([disabled])',
  ].join(',');

  return Array.from(container.querySelectorAll<HTMLElement>(selector)).filter(
    (el) => !el.hasAttribute('disabled') && el.getAttribute('aria-hidden') !== 'true' && el.tabIndex !== -1,
  );
}

export interface UseHistoryDrawerOptions {
  hasNestedModalOpen?: boolean;
}

export interface UseHistoryDrawerReturn {
  showHistorySidebar: boolean;
  isHistorySidebarClosing: boolean;
  openHistorySidebar: () => void;
  closeHistorySidebar: () => void;
  drawerRef: RefObject<HTMLDivElement>;
  closeButtonRef: RefObject<HTMLButtonElement>;
  triggerRef: RefObject<HTMLButtonElement>;
}

export function useHistoryDrawer(options: UseHistoryDrawerOptions = {}): UseHistoryDrawerReturn {
  const { hasNestedModalOpen = false } = options;

  const [showHistorySidebar, setShowHistorySidebar] = useState<boolean>(false);
  const [isHistorySidebarClosing, setIsHistorySidebarClosing] = useState<boolean>(false);

  const historyCloseTimerRef = useRef<number | null>(null);
  const drawerRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const previousActiveElementRef = useRef<HTMLElement | null>(null);

  const wasHistoryOpenRef = useRef(false);
  const hasOpenedHistoryRef = useRef(false);

  const openHistorySidebar = useCallback(() => {
    if (document.activeElement instanceof HTMLElement) {
      previousActiveElementRef.current = document.activeElement;
    }
    if (historyCloseTimerRef.current !== null) {
      window.clearTimeout(historyCloseTimerRef.current);
      historyCloseTimerRef.current = null;
    }
    setIsHistorySidebarClosing(false);
    setShowHistorySidebar(true);
  }, []);

  const closeHistorySidebar = useCallback(() => {
    if (!showHistorySidebar || isHistorySidebarClosing) return;
    setIsHistorySidebarClosing(true);
    historyCloseTimerRef.current = window.setTimeout(() => {
      setShowHistorySidebar(false);
      setIsHistorySidebarClosing(false);
      historyCloseTimerRef.current = null;
    }, 240);
  }, [showHistorySidebar, isHistorySidebarClosing]);

  useEffect(() => {
    if (showHistorySidebar && !wasHistoryOpenRef.current) {
      hasOpenedHistoryRef.current = true;
      if (!previousActiveElementRef.current && document.activeElement instanceof HTMLElement) {
        previousActiveElementRef.current = document.activeElement;
      }
    }
    wasHistoryOpenRef.current = showHistorySidebar;
  }, [showHistorySidebar]);

  useEffect(() => {
    return () => {
      if (historyCloseTimerRef.current !== null) {
        window.clearTimeout(historyCloseTimerRef.current);
      }
    };
  }, []);

  // Initial focus entry into history drawer
  useEffect(() => {
    if (!showHistorySidebar || isHistorySidebarClosing || hasNestedModalOpen) return;

    const timer = requestAnimationFrame(() => {
      const drawer = drawerRef.current;
      if (!drawer) return;
      if (closeButtonRef.current && !closeButtonRef.current.disabled) {
        closeButtonRef.current.focus();
      } else {
        const focusable = getFocusableElements(drawer);
        if (focusable[0]) {
          focusable[0].focus();
        } else {
          drawer.focus();
        }
      }
    });

    return () => cancelAnimationFrame(timer);
  }, [showHistorySidebar, isHistorySidebarClosing, hasNestedModalOpen]);

  // Restore focus to trigger when drawer closes
  useEffect(() => {
    if (!hasOpenedHistoryRef.current) return;
    if (!showHistorySidebar && !isHistorySidebarClosing) {
      const priorElement = previousActiveElementRef.current;
      if (priorElement && document.contains(priorElement)) {
        priorElement.focus();
      } else if (triggerRef.current && document.contains(triggerRef.current)) {
        triggerRef.current.focus();
      }
      previousActiveElementRef.current = null;
    }
  }, [showHistorySidebar, isHistorySidebarClosing]);

  // Focus containment and Escape handling for history drawer
  useEffect(() => {
    if (!showHistorySidebar || isHistorySidebarClosing || hasNestedModalOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      const drawer = drawerRef.current;
      if (!drawer) return;

      if (e.key === 'Escape') {
        e.preventDefault();
        closeHistorySidebar();
        return;
      }

      if (e.key === 'Tab') {
        const focusableElements = getFocusableElements(drawer);
        if (focusableElements.length === 0) {
          e.preventDefault();
          return;
        }

        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];
        const activeEl = document.activeElement;

        if (e.shiftKey) {
          if (activeEl === firstElement || !drawer.contains(activeEl)) {
            e.preventDefault();
            lastElement.focus();
          }
        } else {
          if (activeEl === lastElement || !drawer.contains(activeEl)) {
            e.preventDefault();
            firstElement.focus();
          }
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showHistorySidebar, isHistorySidebarClosing, hasNestedModalOpen, closeHistorySidebar]);

  return {
    showHistorySidebar,
    isHistorySidebarClosing,
    openHistorySidebar,
    closeHistorySidebar,
    drawerRef,
    closeButtonRef,
    triggerRef,
  };
}
