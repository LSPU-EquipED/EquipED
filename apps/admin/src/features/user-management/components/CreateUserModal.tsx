import { useState, useEffect } from 'react';
import { Eye, EyeSlash, WarningCircle, X } from '@phosphor-icons/react';
import { Button, cn, usePresence } from '@equiped/ui';
import { useCreateUser } from '../hooks/useAdminUsers';
import type { AdminUserCreateBody } from '../types';
import { normalizeUserEmail, validateUserEmail } from '../utils/userEmail';

interface CreateUserModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CreateUserModal({ open, onOpenChange }: CreateUserModalProps) {
  const { isMounted, isAnimating } = usePresence({ isOpen: open, durationMs: 240 });
  const createUser = useCreateUser();
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState<AdminUserCreateBody>({
    name: '',
    email: '',
    password: '',
    role: 'faculty',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (open) {
      setFormData({ name: '', email: '', password: '', role: 'faculty' });
      setErrors({});
      setShowPassword(false);
    }
  }, [open]);

  const handleClose = () => {
    if (createUser.isPending) return;
    setFormData({ name: '', email: '', password: '', role: 'faculty' });
    setErrors({});
    onOpenChange(false);
  };

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !createUser.isPending) handleClose();
    };
    if (isMounted) {
      window.addEventListener('keydown', handleKey);
      return () => window.removeEventListener('keydown', handleKey);
    }
  }, [isMounted, createUser.isPending]);

  const validate = (): boolean => {
    const nextErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      nextErrors.name = 'Name is required.';
    }

    const emailError = validateUserEmail(formData.email);
    if (emailError) {
      nextErrors.email = emailError;
    }

    if (!formData.password) {
      nextErrors.password = 'Password is required.';
    } else if (formData.password.length < 8) {
      nextErrors.password = 'Password must be at least 8 characters.';
    } else if (formData.password.length > 256) {
      nextErrors.password = 'Password must be 256 characters or fewer.';
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!validate()) return;

    try {
      await createUser.mutateAsync({ ...formData, email: normalizeUserEmail(formData.email) });
      setFormData({ name: '', email: '', password: '', role: 'faculty' });
      onOpenChange(false);
    } catch {
      // Error is handled by the mutation
    }
  };

  if (!isMounted) return null;

  return (
    <div
      className={cn(
        'fixed inset-0 z-50 flex justify-end bg-black/50 backdrop-blur-xs transition-opacity duration-240 ease-out',
        isAnimating ? 'opacity-100' : 'opacity-0 pointer-events-none',
      )}
      onClick={handleClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-user-modal-title"
        className={cn(
          'w-full sm:max-w-md h-full bg-surface border-l border-border shadow-2xl flex flex-col justify-between overflow-hidden',
          isAnimating ? 'animate-ledger-drawer-in' : 'animate-ledger-drawer-out',
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Pinned Drawer Header */}
        <div className="flex items-start justify-between px-6 py-5 border-b border-border bg-surface shrink-0">
          <div>
            <h2 id="create-user-modal-title" className="text-base sm:text-lg font-semibold text-text">
              Create Account
            </h2>
            <p className="text-xs text-text-muted mt-1 leading-relaxed">
              Add a new user to the system and configure their role and permissions.
            </p>
          </div>
          <button
            type="button"
            onClick={handleClose}
            disabled={createUser.isPending}
            className="size-8 inline-flex items-center justify-center rounded-sm text-text-muted hover:text-text hover:bg-surface-subtle transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer disabled:opacity-50"
            aria-label="Close dialog"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>

        {/* Scrollable Form Body with Pinned Footer */}
        <form onSubmit={handleSubmit} className="flex-1 flex flex-col justify-between min-h-0">
          <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4.5">
            {createUser.isError ? (
              <div
                role="alert"
                className="rounded-sm border border-destructive/30 bg-destructive-soft px-3.5 py-2.5 text-xs font-medium text-destructive flex items-center gap-2"
              >
                <WarningCircle className="size-4 shrink-0" aria-hidden="true" />
                <span>Failed to create user. Please try again.</span>
              </div>
            ) : null}

            {/* Full Name */}
            <div className="space-y-1.5">
              <label
                htmlFor="user-name"
                className="block text-xs font-semibold text-text"
              >
                Full Name <span className="text-destructive">*</span>
              </label>
              <input
                id="user-name"
                value={formData.name}
                onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
                placeholder="Juan Dela Cruz"
                disabled={createUser.isPending}
                className={cn(
                  'h-10 w-full rounded-sm border border-input bg-surface px-3 text-sm font-medium text-text placeholder:text-text-muted/60 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-transparent disabled:cursor-not-allowed disabled:opacity-50',
                  errors.name && 'border-destructive focus-visible:ring-destructive',
                )}
                aria-invalid={!!errors.name}
                aria-describedby={errors.name ? 'user-name-error' : undefined}
              />
              {errors.name ? (
                <p id="user-name-error" className="text-xs font-medium text-destructive">
                  {errors.name}
                </p>
              ) : null}
            </div>

            {/* Email */}
            <div className="space-y-1.5">
              <label
                htmlFor="user-email"
                className="block text-xs font-semibold text-text"
              >
                Email <span className="text-destructive">*</span>
              </label>
              <input
                id="user-email"
                type="email"
                maxLength={40}
                inputMode="email"
                value={formData.email}
                onChange={(e) => setFormData((prev) => ({ ...prev, email: e.target.value }))}
                placeholder="juan@lspu.edu.ph"
                disabled={createUser.isPending}
                className={cn(
                  'h-10 w-full rounded-sm border border-input bg-surface px-3 text-sm font-medium text-text placeholder:text-text-muted/60 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-transparent disabled:cursor-not-allowed disabled:opacity-50',
                  errors.email && 'border-destructive focus-visible:ring-destructive',
                )}
                aria-invalid={!!errors.email}
                aria-describedby={errors.email ? 'user-email-error' : undefined}
              />
              {errors.email ? (
                <p id="user-email-error" className="text-xs font-medium text-destructive">
                  {errors.email}
                </p>
              ) : null}
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <label
                htmlFor="user-password"
                className="block text-xs font-semibold text-text"
              >
                Password <span className="text-destructive">*</span>
              </label>
              <div className="relative">
                <input
                  id="user-password"
                  type={showPassword ? 'text' : 'password'}
                  maxLength={256}
                  value={formData.password}
                  onChange={(e) => setFormData((prev) => ({ ...prev, password: e.target.value }))}
                  placeholder="At least 8 characters"
                  disabled={createUser.isPending}
                  className={cn(
                    'h-10 w-full rounded-sm border border-input bg-surface pl-3 pr-10 text-sm font-medium text-text placeholder:text-text-muted/60 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-transparent disabled:cursor-not-allowed disabled:opacity-50',
                    errors.password && 'border-destructive focus-visible:ring-destructive',
                  )}
                  aria-invalid={!!errors.password}
                  aria-describedby={errors.password ? 'user-password-error' : undefined}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text cursor-pointer p-1 rounded-xs transition-colors"
                  title={showPassword ? 'Hide password' : 'Show password'}
                  tabIndex={-1}
                >
                  {showPassword ? <EyeSlash className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
              {errors.password ? (
                <p id="user-password-error" className="text-xs font-medium text-destructive">
                  {errors.password}
                </p>
              ) : null}
            </div>

            {/* Role */}
            <div className="space-y-1.5">
              <label
                htmlFor="user-role"
                className="block text-xs font-semibold text-text"
              >
                Role
              </label>
              <select
                id="user-role"
                value={formData.role}
                disabled={createUser.isPending}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, role: e.target.value as 'admin' | 'faculty' }))
                }
                className="h-10 w-full rounded-sm border border-input bg-surface px-3 text-sm font-medium text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
              >
                <option value="faculty">Faculty</option>
                <option value="admin">Admin</option>
              </select>
            </div>

            {/* Evaluator Permissions (Faculty Only) */}
            {formData.role === 'faculty' && (
              <div className="space-y-2.5 pt-3 border-t border-border">
                <div>
                  <span className="block text-xs font-semibold text-text">
                    Evaluator Permissions <span className="font-normal text-text-muted">(Optional)</span>
                  </span>
                  <p className="text-[11px] text-text-muted mt-0.5">
                    Assign which specialist desks this faculty member can evaluate (if none selected, all desks remain accessible):
                  </p>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                  {[
                    { id: 'sme', code: 'SME', label: 'Subject Matter Expert' },
                    { id: 'coordinator', code: 'PC', label: 'Program Coordinator' },
                    { id: 'gad', code: 'GAD', label: 'Gender & Development' },
                    { id: 'itso', code: 'ITSO', label: 'Innovation & Tech Support' },
                  ].map((spec) => {
                    const isChecked = (formData.evaluator_permissions || []).includes(spec.id);
                    return (
                      <label
                        key={spec.id}
                        className={cn(
                          'flex items-center gap-2.5 rounded-sm border p-2.5 transition-all cursor-pointer select-none',
                          isChecked
                            ? 'border-primary/40 bg-primary-soft/30 text-text'
                            : 'border-border bg-surface hover:bg-surface-subtle text-text',
                        )}
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          disabled={createUser.isPending}
                          onChange={(e) => {
                            const cur = formData.evaluator_permissions || [];
                            const next = e.target.checked
                              ? [...cur, spec.id]
                              : cur.filter((x) => x !== spec.id);
                            setFormData((prev) => ({ ...prev, evaluator_permissions: next }));
                          }}
                          className="size-4 rounded-xs accent-primary cursor-pointer"
                        />
                        <div className="flex flex-col min-w-0">
                          <span className="font-semibold text-text text-xs leading-tight">{spec.code}</span>
                          <span className="text-[11px] text-text-muted truncate leading-tight mt-0.5">{spec.label}</span>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Pinned Drawer Footer */}
          <div className="px-6 py-4 border-t border-border bg-surface-subtle/40 shrink-0 flex items-center justify-end gap-2.5">
            <Button
              type="button"
              variant="secondary"
              size="md"
              onClick={handleClose}
              disabled={createUser.isPending}
              className="text-xs font-semibold"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="md"
              isLoading={createUser.isPending}
              disabled={createUser.isPending}
              className="text-xs font-semibold gap-1.5"
            >
              Create Account
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
