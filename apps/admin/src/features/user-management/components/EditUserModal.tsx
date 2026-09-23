import { useState, useEffect } from 'react';
import { WarningCircle, X } from '@phosphor-icons/react';
import { Button, cn, usePresence } from '@equiped/ui';
import { useUpdateUser } from '../hooks/useAdminUsers';
import type { AdminUserResponse, AdminUserUpdateBody } from '../types';
import { normalizeUserEmail, validateUserEmail } from '../utils/userEmail';

interface EditUserModalProps {
  user: AdminUserResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function EditUserModal(props: EditUserModalProps) {
  return <EditUserModalDialog key={props.user?.user_id ?? 'none'} {...props} />;
}

function EditUserModalDialog({ user, open, onOpenChange }: EditUserModalProps) {
  const { isMounted, isAnimating } = usePresence({ isOpen: open && !!user, durationMs: 240 });
  const updateUser = useUpdateUser();
  const [formData, setFormData] = useState<AdminUserUpdateBody>({
    name: user?.name ?? '',
    email: user?.email ?? '',
    evaluator_permissions: user?.evaluator_permissions || user?.evaluatorPermissions || [],
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (open && user) {
      setFormData({
        name: user.name ?? '',
        email: user.email ?? '',
        evaluator_permissions: user.evaluator_permissions || user.evaluatorPermissions || [],
      });
      setErrors({});
    }
  }, [open, user]);

  const handleClose = () => {
    if (updateUser.isPending) return;
    onOpenChange(false);
  };

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !updateUser.isPending) handleClose();
    };
    if (isMounted) {
      window.addEventListener('keydown', handleKey);
      return () => window.removeEventListener('keydown', handleKey);
    }
  }, [isMounted, updateUser.isPending]);

  const validate = (): boolean => {
    const nextErrors: Record<string, string> = {};

    if (!formData.name?.trim()) {
      nextErrors.name = 'Name is required.';
    }

    const emailError = validateUserEmail(formData.email);
    if (emailError) {
      nextErrors.email = emailError;
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!user) return;
    if (!validate()) return;

    try {
      await updateUser.mutateAsync({
        userId: user.user_id,
        body: { ...formData, email: normalizeUserEmail(formData.email) },
      });
      onOpenChange(false);
    } catch {
      // Error is handled by the mutation
    }
  };

  if (!isMounted || !user) return null;

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
        aria-labelledby="edit-user-modal-title"
        className={cn(
          'w-full sm:max-w-md h-full bg-surface border-l border-border shadow-2xl flex flex-col justify-between overflow-hidden',
          isAnimating ? 'animate-ledger-drawer-in' : 'animate-ledger-drawer-out',
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Pinned Drawer Header */}
        <div className="flex items-start justify-between px-6 py-5 border-b border-border bg-surface shrink-0">
          <div>
            <h2 id="edit-user-modal-title" className="text-base sm:text-lg font-semibold text-text">
              Edit Account
            </h2>
            <p className="text-xs text-text-muted mt-1 leading-relaxed">
              Update account details and evaluator permissions for{' '}
              <span className="font-semibold text-text">{user.name}</span>.
            </p>
          </div>
          <button
            type="button"
            onClick={handleClose}
            disabled={updateUser.isPending}
            className="size-8 inline-flex items-center justify-center rounded-sm text-text-muted hover:text-text hover:bg-surface-subtle transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer disabled:opacity-50"
            aria-label="Close dialog"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>

        {/* Scrollable Form Body with Pinned Footer */}
        <form onSubmit={handleSubmit} className="flex-1 flex flex-col justify-between min-h-0">
          <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4.5">
            {updateUser.isError ? (
              <div
                role="alert"
                className="rounded-sm border border-destructive/30 bg-destructive-soft px-3.5 py-2.5 text-xs font-medium text-destructive flex items-center gap-2"
              >
                <WarningCircle className="size-4 shrink-0" aria-hidden="true" />
                <span>Failed to update user. Please try again.</span>
              </div>
            ) : null}

            {/* Full Name */}
            <div className="space-y-1.5">
              <label
                htmlFor="edit-user-name"
                className="block text-xs font-semibold text-text"
              >
                Full Name <span className="text-destructive">*</span>
              </label>
              <input
                id="edit-user-name"
                value={formData.name}
                onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
                placeholder="Juan Dela Cruz"
                disabled={updateUser.isPending}
                className={cn(
                  'h-10 w-full rounded-sm border border-input bg-surface px-3 text-sm font-medium text-text placeholder:text-text-muted/60 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-transparent disabled:cursor-not-allowed disabled:opacity-50',
                  errors.name && 'border-destructive focus-visible:ring-destructive',
                )}
                aria-invalid={!!errors.name}
                aria-describedby={errors.name ? 'edit-user-name-error' : undefined}
              />
              {errors.name ? (
                <p id="edit-user-name-error" className="text-xs font-medium text-destructive">
                  {errors.name}
                </p>
              ) : null}
            </div>

            {/* Email */}
            <div className="space-y-1.5">
              <label
                htmlFor="edit-user-email"
                className="block text-xs font-semibold text-text"
              >
                Email <span className="text-destructive">*</span>
              </label>
              <input
                id="edit-user-email"
                type="email"
                maxLength={40}
                inputMode="email"
                value={formData.email}
                onChange={(e) => setFormData((prev) => ({ ...prev, email: e.target.value }))}
                placeholder="juan@lspu.edu.ph"
                disabled={updateUser.isPending}
                className={cn(
                  'h-10 w-full rounded-sm border border-input bg-surface px-3 text-sm font-medium text-text placeholder:text-text-muted/60 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-transparent disabled:cursor-not-allowed disabled:opacity-50',
                  errors.email && 'border-destructive focus-visible:ring-destructive',
                )}
                aria-invalid={!!errors.email}
                aria-describedby={errors.email ? 'edit-user-email-error' : undefined}
              />
              {errors.email ? (
                <p id="edit-user-email-error" className="text-xs font-medium text-destructive">
                  {errors.email}
                </p>
              ) : null}
            </div>

            {/* Evaluator Permissions (Faculty Only) */}
            {user.role === 'faculty' && (
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
                          disabled={updateUser.isPending}
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
              disabled={updateUser.isPending}
              className="text-xs font-semibold"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="md"
              isLoading={updateUser.isPending}
              disabled={updateUser.isPending}
              className="text-xs font-semibold gap-1.5"
            >
              Save Changes
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
