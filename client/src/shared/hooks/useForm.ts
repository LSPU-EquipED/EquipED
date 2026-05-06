import { type ChangeEvent, type FormEvent, useCallback, useState } from 'react';

type InputElement = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;

type FormErrors<TValues> = Partial<Record<keyof TValues, string>>;

interface UseFormOptions<TValues> {
  initialValues: TValues;
  onSubmit?: (values: TValues) => void | Promise<void>;
  validate?: (values: TValues) => FormErrors<TValues>;
}

export function useForm<TValues extends Record<string, unknown>>({
  initialValues,
  onSubmit,
  validate,
}: UseFormOptions<TValues>) {
  const [values, setValues] = useState<TValues>(initialValues);
  const [errors, setErrors] = useState<FormErrors<TValues>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const setValue = useCallback(<K extends keyof TValues>(field: K, value: TValues[K]) => {
    setValues((current) => ({ ...current, [field]: value }));
  }, []);

  const handleChange = useCallback((event: ChangeEvent<InputElement>) => {
    const { name, type } = event.target;
    const checked = 'checked' in event.target ? event.target.checked : false;
    const nextValue = type === 'checkbox' ? checked : event.target.value;

    setValues((current) => ({
      ...current,
      [name]: nextValue,
    }));
  }, []);

  const resetForm = useCallback(() => {
    setValues(initialValues);
    setErrors({});
    setIsSubmitting(false);
  }, [initialValues]);

  const handleSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();

      const validationErrors = validate ? validate(values) : {};
      setErrors(validationErrors);

      if (Object.keys(validationErrors).length > 0 || !onSubmit) {
        return;
      }

      setIsSubmitting(true);

      try {
        await onSubmit(values);
      } finally {
        setIsSubmitting(false);
      }
    },
    [onSubmit, validate, values],
  );

  return {
    values,
    errors,
    isSubmitting,
    setValues,
    setValue,
    setErrors,
    handleChange,
    handleSubmit,
    resetForm,
  };
}

export type { FormErrors, UseFormOptions };
