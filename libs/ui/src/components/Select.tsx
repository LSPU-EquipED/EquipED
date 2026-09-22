import React, { forwardRef, useId, type ReactNode } from 'react';
import { CaretDown } from '@phosphor-icons/react';
import { cn } from '../utils';
import { SELECT_STYLES } from '../theme';

export interface SelectOption {
  value: string | number;
  label: string;
  disabled?: boolean;
}

export interface SelectProps extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'size'> {
  label?: string;
  inlineLabel?: boolean;
  hint?: string;
  error?: string;
  icon?: ReactNode;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'subtle' | 'ghost';
  options?: SelectOption[];
  containerClassName?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  (
    {
      className,
      containerClassName,
      label,
      inlineLabel = false,
      hint,
      error,
      icon,
      size = 'sm',
      variant = 'default',
      options,
      children,
      id: idProp,
      required,
      disabled,
      ...props
    },
    ref,
  ) => {
    const generatedId = useId();
    const id = idProp ?? (label ? generatedId : undefined);
    const hasFieldWrapper = Boolean(label || hint || error);

    const sizeClass = SELECT_STYLES.sizes[size] ?? SELECT_STYLES.sizes.sm;
    const variantClass = SELECT_STYLES.variants[variant] ?? SELECT_STYLES.variants.default;

    const caretSizes = {
      sm: 'size-3.5 right-2',
      md: 'size-4 right-2.5',
      lg: 'size-4.5 right-3',
    };

    const iconLeftPaddings = {
      sm: 'pl-7.5',
      md: 'pl-8.5',
      lg: 'pl-9.5',
    };

    const iconSizes = {
      sm: 'size-3.5 left-2.5',
      md: 'size-4 left-2.5',
      lg: 'size-4.5 left-3',
    };

    const selectElement = (
      <div
        className={cn(
          'relative inline-flex items-center w-full',
          !hasFieldWrapper && containerClassName,
        )}
      >
        {icon ? (
          <span
            className={cn(
              'pointer-events-none absolute text-text-muted shrink-0 z-10 flex items-center justify-center',
              iconSizes[size],
            )}
            aria-hidden="true"
          >
            {icon}
          </span>
        ) : null}

        <select
          ref={ref}
          id={id}
          required={required}
          disabled={disabled}
          aria-invalid={Boolean(error)}
          aria-describedby={
            error ? `${id}-error` : hint ? `${id}-hint` : undefined
          }
          className={cn(
            SELECT_STYLES.base,
            sizeClass,
            variantClass,
            Boolean(icon) && iconLeftPaddings[size],
            error && 'border-destructive focus-visible:ring-destructive',
            className,
          )}
          {...props}
        >
          {options
            ? options.map((opt) => (
                <option key={opt.value} value={opt.value} disabled={opt.disabled}>
                  {opt.label}
                </option>
              ))
            : children}
        </select>

        <CaretDown
          className={cn(
            'pointer-events-none absolute text-text-muted transition-transform shrink-0',
            caretSizes[size],
          )}
          aria-hidden="true"
        />
      </div>
    );

    if (inlineLabel && label) {
      return (
        <div className={cn('inline-flex items-center gap-1.5', containerClassName)}>
          <label htmlFor={id} className={SELECT_STYLES.inlineLabel}>
            {label}
            {required ? <span className="ml-0.5 text-destructive">*</span> : null}
          </label>
          {selectElement}
          {error ? (
            <p id={`${id}-error`} className={SELECT_STYLES.error} role="alert">
              {error}
            </p>
          ) : null}
        </div>
      );
    }

    if (!label && !hint && !error) {
      return selectElement;
    }

    return (
      <div className={cn('w-full', containerClassName)}>
        {label ? (
          <label htmlFor={id} className={SELECT_STYLES.label}>
            {label}
            {required ? <span className="ml-1 text-destructive">*</span> : null}
          </label>
        ) : null}
        {selectElement}
        {error ? (
          <p id={`${id}-error`} className={SELECT_STYLES.error} role="alert">
            {error}
          </p>
        ) : hint ? (
          <p id={`${id}-hint`} className={SELECT_STYLES.hint}>
            {hint}
          </p>
        ) : null}
      </div>
    );
  },
);

Select.displayName = 'Select';

export const NativeSelect = Select;
export type NativeSelectProps = SelectProps;
