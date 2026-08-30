/**
 * Reusable Design System Tokens & Tailwind Class Mappings
 * Conforms to Google-spec DESIGN.md ("The Contemporary Faculty Ledger")
 */

export const TYPOGRAPHY = {
  display: 'text-[32px] font-bold leading-[1.15] tracking-[-0.02em] text-text',
  headingLg: 'text-[28px] font-bold leading-[1.25] tracking-[-0.015em] text-text',
  headingMd: 'text-[20px] font-semibold leading-[1.35] tracking-[-0.01em] text-text',
  headingSm: 'text-[16px] font-semibold leading-[1.4] tracking-normal text-text',
  bodyMd: 'text-[15px] font-normal leading-[1.6] tracking-normal text-text',
  bodySm: 'text-[14px] font-medium leading-[1.4] tracking-normal text-text',
  labelSm: 'text-[12px] font-semibold leading-[1.4] tracking-[0.04em] text-text',
  labelMuted: 'text-[12px] font-semibold leading-[1.4] tracking-[0.04em] text-text-muted',
  dataMd: 'text-[13px] font-medium leading-[1.35] tabular-nums text-text',
} as const;

export const STATUS_VARIANTS = {
  success: {
    container: 'bg-success-soft text-success border border-success/20',
    dot: 'bg-success',
    text: 'text-success',
  },
  info: {
    container: 'bg-info-soft text-info border border-info/20',
    dot: 'bg-info',
    text: 'text-info',
  },
  warning: {
    container: 'bg-warning-soft text-warning border border-warning/20',
    dot: 'bg-warning',
    text: 'text-warning',
  },
  destructive: {
    container: 'bg-destructive-soft text-destructive border border-destructive/20',
    dot: 'bg-destructive',
    text: 'text-destructive',
  },
  neutral: {
    container: 'bg-surface-subtle text-text-muted border border-border',
    dot: 'bg-text-muted',
    text: 'text-text-muted',
  },
  accent: {
    container: 'bg-accent-soft text-accent-foreground border border-accent/30',
    dot: 'bg-accent',
    text: 'text-accent-foreground',
  },
} as const;

export type StatusVariant = keyof typeof STATUS_VARIANTS;

export const BUTTON_STYLES = {
  base: 'inline-flex items-center justify-center gap-2 rounded-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-50 select-none cursor-pointer',
  variants: {
    primary: 'bg-primary text-primary-foreground hover:bg-primary-strong shadow-none active:bg-primary-strong',
    secondary: 'bg-surface text-text border border-border hover:bg-surface-subtle shadow-none active:bg-surface-subtle',
    destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90 shadow-none',
    outline: 'bg-transparent text-text border border-border hover:bg-surface-subtle',
    ghost: 'bg-transparent text-text hover:bg-surface-subtle',
  },
  sizes: {
    sm: 'h-8 px-3 text-xs',
    md: 'h-10 px-4 text-sm',
    lg: 'h-11 px-5 text-sm',
    icon: 'size-10 p-0',
    iconSm: 'size-8 p-0',
  },
} as const;

export const CARD_STYLES = {
  ledger: 'rounded-md border border-border bg-surface shadow-none overflow-hidden',
  flat: 'rounded-sm border border-border bg-surface',
  header: 'flex items-center justify-between border-b border-border bg-surface px-6 py-4',
  content: 'p-6',
  footer: 'flex items-center justify-end gap-3 border-t border-border bg-surface-subtle px-6 py-3',
} as const;

export const INPUT_STYLES = {
  base: 'flex h-10 w-full rounded-sm border border-input bg-surface px-3 py-2 text-sm text-text placeholder:text-text-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-transparent disabled:cursor-not-allowed disabled:opacity-50',
  label: 'mb-1.5 block text-xs font-semibold text-text',
  hint: 'mt-1.5 text-xs text-text-muted',
  error: 'mt-1.5 text-xs font-medium text-destructive',
} as const;

export const TABLE_STYLES = {
  wrapper: 'w-full overflow-x-auto rounded-md border border-border bg-surface',
  table: 'w-full text-left border-collapse',
  thead: 'border-b border-border bg-surface-subtle text-[11px] font-semibold uppercase tracking-wider text-text-muted',
  th: 'px-4 py-3 text-left font-semibold text-text-muted',
  tbody: 'divide-y divide-border bg-surface text-sm text-text',
  tr: 'transition-colors hover:bg-surface-subtle/70',
  td: 'px-4 py-3 text-sm text-text',
  tdData: 'px-4 py-3 text-sm tabular-nums text-text',
} as const;
