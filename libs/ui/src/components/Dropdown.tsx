import React, {
  forwardRef,
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { CaretDown, Check } from '@phosphor-icons/react';
import { cn } from '../utils';
import { DROPDOWN_STYLES } from '../theme';
import { useClickOutside } from '../hooks';

export interface DropdownOption<T extends string | number = string> {
  value: T;
  label: string;
  disabled?: boolean;
  icon?: ReactNode;
  description?: string;
}

export interface DropdownProps<T extends string | number = string> {
  id?: string;
  name?: string;
  value?: T;
  defaultValue?: T;
  onChange?: (value: T) => void;
  options: DropdownOption<T>[];
  placeholder?: string;
  label?: string;
  inlineLabel?: boolean;
  hint?: string;
  error?: string;
  icon?: ReactNode;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'subtle' | 'ghost';
  align?: 'left' | 'right';
  disabled?: boolean;
  required?: boolean;
  className?: string;
  containerClassName?: string;
  menuClassName?: string;
  'aria-label'?: string;
}

function DropdownInner<T extends string | number = string>(
  {
    id: idProp,
    name,
    value: controlledValue,
    defaultValue,
    onChange,
    options = [],
    placeholder = 'Select an option',
    label,
    inlineLabel = false,
    hint,
    error,
    icon,
    size = 'sm',
    variant = 'default',
    align = 'left',
    disabled = false,
    required = false,
    className,
    containerClassName,
    menuClassName,
    'aria-label': ariaLabelProp,
  }: DropdownProps<T>,
  ref: React.ForwardedRef<HTMLButtonElement>,
) {
  const generatedId = useId();
  const id = idProp ?? generatedId;
  const listId = `${id}-listbox`;

  const [isOpen, setIsOpen] = useState(false);
  const [internalValue, setInternalValue] = useState<T | undefined>(defaultValue);
  const isControlled = controlledValue !== undefined;
  const activeValue = isControlled ? controlledValue : internalValue;

  const containerRef = useRef<HTMLDivElement>(null);
  const internalTriggerRef = useRef<HTMLButtonElement | null>(null);
  const listboxRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);

  // Find selected option
  const selectedOption = useMemo(
    () => options.find((opt) => String(opt.value) === String(activeValue)),
    [options, activeValue],
  );

  const selectedIndex = useMemo(
    () => options.findIndex((opt) => String(opt.value) === String(activeValue)),
    [options, activeValue],
  );

  const [highlightedIndex, setHighlightedIndex] = useState<number>(
    selectedIndex >= 0 ? selectedIndex : 0,
  );

  // Sync highlighted index when selected option changes or opens
  useEffect(() => {
    if (isOpen) {
      setHighlightedIndex(selectedIndex >= 0 ? selectedIndex : 0);
    }
  }, [isOpen, selectedIndex]);

  // Scroll highlighted item into view
  useEffect(() => {
    if (isOpen && highlightedIndex >= 0 && itemRefs.current[highlightedIndex]) {
      itemRefs.current[highlightedIndex]?.scrollIntoView?.({ block: 'nearest' });
    }
  }, [isOpen, highlightedIndex]);

  // Focus listbox when opened
  useEffect(() => {
    if (isOpen) {
      listboxRef.current?.focus();
    }
  }, [isOpen]);

  // Handle outside clicks
  useClickOutside(containerRef, () => {
    setIsOpen(false);
  }, { enabled: isOpen });

  const selectOption = useCallback(
    (opt: DropdownOption<T>) => {
      if (opt.disabled) return;
      if (!isControlled) {
        setInternalValue(opt.value);
      }
      onChange?.(opt.value);
      setIsOpen(false);
      internalTriggerRef.current?.focus();
    },
    [isControlled, onChange],
  );

  const handleTriggerKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (disabled) return;

    if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
      }
    } else if (e.key === 'Escape' && isOpen) {
      e.preventDefault();
      setIsOpen(false);
    }
  };

  const handleListKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Escape' || e.key === 'Tab') {
      if (e.key === 'Escape') e.preventDefault();
      setIsOpen(false);
      internalTriggerRef.current?.focus();
      return;
    }

    const enabledIndices = options
      .map((opt, idx) => (opt.disabled ? -1 : idx))
      .filter((idx) => idx !== -1);

    if (enabledIndices.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex((prev) => {
        const nextPos = enabledIndices.findIndex((idx) => idx > prev);
        return nextPos !== -1 ? enabledIndices[nextPos] : enabledIndices[0];
      });
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex((prev) => {
        const prevIndices = enabledIndices.filter((idx) => idx < prev);
        return prevIndices.length > 0
          ? prevIndices[prevIndices.length - 1]
          : enabledIndices[enabledIndices.length - 1];
      });
    } else if (e.key === 'Home') {
      e.preventDefault();
      setHighlightedIndex(enabledIndices[0]);
    } else if (e.key === 'End') {
      e.preventDefault();
      setHighlightedIndex(enabledIndices[enabledIndices.length - 1]);
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      const targetOpt = options[highlightedIndex];
      if (targetOpt && !targetOpt.disabled) {
        selectOption(targetOpt);
      }
    }
  };

  const triggerSizeClass = DROPDOWN_STYLES.sizes[size] ?? DROPDOWN_STYLES.sizes.sm;
  const triggerVariantClass = DROPDOWN_STYLES.variants[variant] ?? DROPDOWN_STYLES.variants.default;
  const itemSizeClass = DROPDOWN_STYLES.itemSizes[size] ?? DROPDOWN_STYLES.itemSizes.sm;

  const caretSizes = {
    sm: 'size-3 text-text-muted',
    md: 'size-3.5 text-text-muted',
    lg: 'size-4 text-text-muted',
  };

  const effectiveAriaLabel =
    ariaLabelProp ??
    (label ? undefined : 'Select option');

  const triggerButton = (
    <button
      ref={(node) => {
        internalTriggerRef.current = node;
        if (typeof ref === 'function') ref(node);
        else if (ref) (ref as React.MutableRefObject<HTMLButtonElement | null>).current = node;
      }}
      id={id}
      type="button"
      disabled={disabled}
      aria-haspopup="listbox"
      aria-expanded={isOpen}
      aria-controls={isOpen ? listId : undefined}
      aria-label={effectiveAriaLabel}
      aria-invalid={Boolean(error)}
      aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
      onClick={() => {
        if (!disabled) setIsOpen((prev) => !prev);
      }}
      onKeyDown={handleTriggerKeyDown}
      className={cn(
        DROPDOWN_STYLES.trigger,
        triggerSizeClass,
        triggerVariantClass,
        error && 'border-destructive focus-visible:ring-destructive',
        className,
      )}
    >
      <span className="inline-flex items-center gap-1.5 truncate">
        {icon ? <span className="shrink-0 text-text-muted" aria-hidden="true">{icon}</span> : null}
        <span className="truncate">
          {selectedOption ? selectedOption.label : <span className="text-text-muted">{placeholder}</span>}
        </span>
      </span>

      <CaretDown
        className={cn(
          caretSizes[size],
          'shrink-0 transition-transform duration-150',
          isOpen && 'rotate-180',
        )}
        aria-hidden="true"
      />
    </button>
  );

  const popoverMenu = isOpen ? (
    <div
      ref={listboxRef}
      id={listId}
      role="listbox"
      tabIndex={-1}
      aria-label={label ?? ariaLabelProp ?? 'Options'}
      aria-activedescendant={
        highlightedIndex >= 0 ? `${id}-opt-${highlightedIndex}` : undefined
      }
      onKeyDown={handleListKeyDown}
      className={cn(
        DROPDOWN_STYLES.menu,
        align === 'right' ? 'right-0' : 'left-0',
        menuClassName,
      )}
    >
      {options.map((opt, index) => {
        const isSelected = String(opt.value) === String(activeValue);
        const isHighlighted = index === highlightedIndex;

        return (
          <button
            key={String(opt.value)}
            ref={(el) => {
              itemRefs.current[index] = el;
            }}
            id={`${id}-opt-${index}`}
            type="button"
            role="option"
            aria-selected={isSelected}
            aria-disabled={opt.disabled}
            disabled={opt.disabled}
            tabIndex={-1}
            onClick={() => selectOption(opt)}
            onMouseEnter={() => setHighlightedIndex(index)}
            className={cn(
              DROPDOWN_STYLES.item,
              itemSizeClass,
              isSelected
                ? DROPDOWN_STYLES.itemSelected
                : isHighlighted
                  ? DROPDOWN_STYLES.itemHighlighted
                  : DROPDOWN_STYLES.itemDefault,
              opt.disabled && 'opacity-40 cursor-not-allowed pointer-events-none',
            )}
          >
            <span className="flex min-w-0 flex-col">
              <span className="flex items-center gap-2 truncate">
                {opt.icon ? <span className="shrink-0" aria-hidden="true">{opt.icon}</span> : null}
                <span className="truncate">{opt.label}</span>
              </span>
              {opt.description ? (
                <span className="text-[11px] font-normal text-text-muted mt-0.5 truncate">
                  {opt.description}
                </span>
              ) : null}
            </span>

            {isSelected ? (
              <Check className="size-3.5 text-primary shrink-0 ml-2" aria-hidden="true" />
            ) : null}
          </button>
        );
      })}
    </div>
  ) : null;

  // Hidden input for native form submission support
  const hiddenInput = name ? (
    <input
      type="hidden"
      name={name}
      value={activeValue !== undefined ? String(activeValue) : ''}
      required={required}
      disabled={disabled}
    />
  ) : null;

  if (inlineLabel && label) {
    return (
      <div className={cn('relative inline-flex items-center gap-1.5', containerClassName)} ref={containerRef}>
        <label htmlFor={id} className={DROPDOWN_STYLES.inlineLabel}>
          {label}
          {required ? <span className="ml-0.5 text-destructive">*</span> : null}
        </label>
        <div className="relative inline-flex items-center">
          {triggerButton}
          {popoverMenu}
        </div>
        {hiddenInput}
        {error ? (
          <p id={`${id}-error`} className={DROPDOWN_STYLES.error} role="alert">
            {error}
          </p>
        ) : null}
      </div>
    );
  }

  if (!label && !hint && !error) {
    return (
      <div className={cn('relative inline-block', containerClassName)} ref={containerRef}>
        {triggerButton}
        {popoverMenu}
        {hiddenInput}
      </div>
    );
  }

  return (
    <div className={cn('relative w-full', containerClassName)} ref={containerRef}>
      {label ? (
        <label htmlFor={id} className={DROPDOWN_STYLES.label}>
          {label}
          {required ? <span className="ml-1 text-destructive">*</span> : null}
        </label>
      ) : null}
      <div className="relative w-full">
        {triggerButton}
        {popoverMenu}
      </div>
      {hiddenInput}
      {error ? (
        <p id={`${id}-error`} className={DROPDOWN_STYLES.error} role="alert">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className={DROPDOWN_STYLES.hint}>
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export const Dropdown = forwardRef(DropdownInner) as <T extends string | number = string>(
  props: DropdownProps<T> & { ref?: React.ForwardedRef<HTMLButtonElement> },
) => React.ReactElement;

export const CustomSelect = Dropdown;
export type CustomSelectProps<T extends string | number = string> = DropdownProps<T>;
