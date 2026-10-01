import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { DotsThree } from '@phosphor-icons/react';
import { Link } from '@tanstack/react-router';
import { Button } from './Button';
import { cn } from '../utils';
import { DROPDOWN_STYLES } from '../theme';
import { useClickOutside } from '../hooks';

const useMenuLayoutEffect = typeof window === 'undefined' ? useEffect : useLayoutEffect;

interface MenuActionBase {
  label: string;
  icon: ReactNode;
  ariaLabel?: string;
  disabled?: boolean;
  destructive?: boolean;
  separatorBefore?: boolean;
}

export type MenuAction = MenuActionBase &
  (
    | { onSelect: () => void; to?: never; href?: never }
    | { to: string; onSelect?: never; href?: never }
    | { href: string; target?: string; rel?: string; onSelect?: never; to?: never }
  );

export function ActionsMenu({ name, actions }: { name: string; actions: MenuAction[] }) {
  const id = useId();
  const [isOpen, setIsOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const focusLast = useRef(false);

  const close = (restoreFocus = false) => {
    setIsOpen(false);
    if (restoreFocus) triggerRef.current?.focus();
  };
  useClickOutside([triggerRef, menuRef], () => close(), { enabled: isOpen });

  useMenuLayoutEffect(() => {
    const trigger = triggerRef.current;
    const menu = menuRef.current;
    if (!isOpen || !trigger || !menu) return;
    const rect = trigger.getBoundingClientRect();
    const gutter = 8;
    const below = window.innerHeight - rect.bottom - gutter * 2;
    const above = rect.top - gutter * 2;
    const openAbove = menu.offsetHeight > below && above > below;
    menu.style.maxHeight = `${Math.max(0, openAbove ? above : below)}px`;
    menu.style.top = `${openAbove ? rect.top - menu.offsetHeight - gutter : rect.bottom + gutter}px`;
    menu.style.left = `${Math.max(gutter, Math.min(rect.right - menu.offsetWidth, window.innerWidth - menu.offsetWidth - gutter))}px`;
    menu.style.visibility = 'visible';
    const items = menu.querySelectorAll<HTMLElement>('[role="menuitem"]:not(:disabled)');
    (focusLast.current ? items[items.length - 1] : items[0])?.focus();
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const onScroll = (event: Event) => {
      if (event.target instanceof Node && menuRef.current?.contains(event.target)) return;
      setIsOpen(false);
    };
    const onResize = () => setIsOpen(false);
    window.addEventListener('scroll', onScroll, true);
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('scroll', onScroll, true);
      window.removeEventListener('resize', onResize);
    };
  }, [isOpen]);

  return (
    <>
      <Button
        ref={triggerRef}
        type="button"
        variant="ghost"
        size="icon"
        aria-label={`Actions for ${name}`}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-controls={isOpen ? id : undefined}
        onClick={() => {
          focusLast.current = false;
          setIsOpen(!isOpen);
        }}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            focusLast.current = event.key === 'ArrowUp';
            setIsOpen(true);
          }
        }}
      >
        <DotsThree className="size-5" weight="bold" aria-hidden="true" />
      </Button>
      {isOpen &&
        createPortal(
          <div
            ref={menuRef}
            id={id}
            role="menu"
            aria-label={`Actions for ${name}`}
            style={{
              position: 'fixed',
              width: '12rem',
              minWidth: 0,
              marginTop: 0,
              visibility: 'hidden',
            }}
            className={DROPDOWN_STYLES.menu}
            onBlur={(event) => {
              if (
                !event.currentTarget.contains(event.relatedTarget) &&
                event.relatedTarget !== triggerRef.current
              )
                close();
            }}
            onKeyDown={(event) => {
              if (event.key === 'Escape' || event.key === 'Tab') {
                if (event.key === 'Escape') event.preventDefault();
                close(true);
                return;
              }
              const items = Array.from(
                event.currentTarget.querySelectorAll<HTMLElement>(
                  '[role="menuitem"]:not(:disabled)',
                ),
              );
              if (!items.length) return;
              const current = items.indexOf(document.activeElement as HTMLElement);
              let next: number;
              if (event.key === 'ArrowDown') next = (current + 1) % items.length;
              else if (event.key === 'ArrowUp') next = (current - 1 + items.length) % items.length;
              else if (event.key === 'Home') next = 0;
              else if (event.key === 'End') next = items.length - 1;
              else return;
              event.preventDefault();
              items[next]?.focus();
            }}
          >
            {actions.map((action) => {
              const className = cn(
                DROPDOWN_STYLES.item,
                DROPDOWN_STYLES.itemSizes.md,
                'justify-start min-h-10 focus-visible:outline-none focus-visible:bg-surface-subtle disabled:cursor-not-allowed disabled:opacity-40',
                action.destructive
                  ? 'text-destructive hover:bg-destructive-soft focus-visible:bg-destructive-soft'
                  : DROPDOWN_STYLES.itemDefault,
                action.separatorBefore && 'mt-1 border-t border-border',
              );
              const content = (
                <>
                  <span aria-hidden="true">{action.icon}</span>
                  {action.label}
                </>
              );
              const itemProps = {
                role: 'menuitem',
                tabIndex: -1,
                className,
                'aria-label': action.ariaLabel,
                onClick: () => close(true),
              };
              if (!action.disabled && action.to) {
                return (
                  <Link key={action.label} to={action.to} {...itemProps}>
                    {content}
                  </Link>
                );
              }
              if (!action.disabled && action.href) {
                return (
                  <a
                    key={action.label}
                    href={action.href}
                    target={action.target}
                    rel={action.rel}
                    {...itemProps}
                  >
                    {content}
                  </a>
                );
              }
              return (
                <button
                  key={action.label}
                  type="button"
                  {...itemProps}
                  disabled={action.disabled}
                  onClick={() => {
                    close(true);
                    action.onSelect?.();
                  }}
                >
                  {content}
                </button>
              );
            })}
          </div>,
          document.body,
        )}
    </>
  );
}
