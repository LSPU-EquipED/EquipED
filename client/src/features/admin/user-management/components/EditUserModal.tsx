import { useState } from 'react';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/components/utils';
import { INPUT_STYLES } from '@/shared/constants/theme';
import { useUpdateUser } from '../hooks/useAdminUsers';
import type { AdminUserResponse, AdminUserUpdateBody } from '../types';

const LSPU_EMAIL_PATTERN = /^[^\s@]+@lspu\.edu\.ph$/i;

interface EditUserModalProps {
  user: AdminUserResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function EditUserModal(props: EditUserModalProps) {
  return <EditUserModalDialog key={`${props.user?.user_id ?? 'none'}-${props.open}`} {...props} />;
}

function EditUserModalDialog({ user, open, onOpenChange }: EditUserModalProps) {
  const updateUser = useUpdateUser();
  const [formData, setFormData] = useState<AdminUserUpdateBody>({
    name: user?.name ?? '',
    email: user?.email ?? '',
    evaluator_permissions: user?.evaluator_permissions || user?.evaluatorPermissions || [],
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = (): boolean => {
    const nextErrors: Record<string, string> = {};

    if (!formData.name?.trim()) {
      nextErrors.name = 'Name is required.';
    }

    if (!formData.email?.trim()) {
      nextErrors.email = 'Email is required.';
    } else if (formData.email.trim().length > 40) {
      nextErrors.email = 'Email must be 40 characters or fewer.';
    } else if (!LSPU_EMAIL_PATTERN.test(formData.email.trim())) {
      nextErrors.email = 'Please use your official @lspu.edu.ph email address.';
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
        body: { ...formData, email: formData.email?.trim().toLowerCase() },
      });
      onOpenChange(false);
    } catch {
      // Error is handled by the mutation
    }
  };

  const handleClose = () => {
    if (updateUser.isPending) return;
    onOpenChange(false);
  };

  if (!open || !user) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-xs"
      onClick={handleClose}
    >
      <div
        className="w-full sm:max-w-md bg-surface border-l border-border p-6 sm:p-8 h-full flex flex-col justify-between overflow-y-auto relative"
        onClick={(e) => e.stopPropagation()}
      >
        <div>
          <div className="flex items-center justify-between pb-4 border-b border-border">
            <h3 className="text-base font-bold uppercase tracking-wider text-text">Edit Account</h3>
            <button
              type="button"
              onClick={handleClose}
              className="text-text-muted hover:text-text text-sm font-semibold uppercase tracking-wider focus-visible:outline-none cursor-pointer"
            >
              Close
            </button>
          </div>
          <p className="text-xs text-text-muted font-medium mt-3 leading-relaxed">
            Update the name and email for {user.name}. Changes apply immediately.
          </p>

          <form onSubmit={handleSubmit} className="mt-6 grid gap-5">
            <div className="space-y-2">
              <label
                htmlFor="edit-user-name"
                className="text-xs font-semibold uppercase tracking-wider text-text-muted"
              >
                Full Name
              </label>
              <input
                id="edit-user-name"
                value={formData.name}
                onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
                placeholder="Juan Dela Cruz"
                className={cn(
                  INPUT_STYLES.base,
                  'font-medium text-text placeholder:text-text-muted',
                  errors.name && 'border-destructive focus-visible:ring-destructive',
                )}
                aria-invalid={!!errors.name}
              />
              {errors.name ? (
                <p className="text-xs font-semibold text-destructive">{errors.name}</p>
              ) : null}
            </div>

            <div className="space-y-2">
              <label
                htmlFor="edit-user-email"
                className="text-xs font-semibold uppercase tracking-wider text-text-muted"
              >
                Email
              </label>
              <input
                id="edit-user-email"
                type="email"
                maxLength={40}
                inputMode="email"
                value={formData.email}
                onChange={(e) => setFormData((prev) => ({ ...prev, email: e.target.value }))}
                placeholder="juan@lspu.edu.ph"
                className={cn(
                  INPUT_STYLES.base,
                  'font-medium text-text placeholder:text-text-muted',
                  errors.email && 'border-destructive focus-visible:ring-destructive',
                )}
                aria-invalid={!!errors.email}
                aria-describedby={errors.email ? 'edit-user-email-error' : undefined}
              />
              {errors.email ? (
                <p id="edit-user-email-error" className="text-xs font-semibold text-destructive">
                  {errors.email}
                </p>
              ) : null}
            </div>
            {user.role === 'faculty' && (
              <div className="space-y-2 pt-1 border-t border-border">
                <span className="text-xs font-semibold uppercase tracking-wider text-text-muted block">
                  Evaluator Permissions
                </span>
                <p className="text-[11px] text-text-muted">
                  Assign which specialist desks this faculty member can evaluate (if none selected, all desks remain accessible):
                </p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {[
                    { id: 'sme', label: 'Subject Matter Expert (SME)' },
                    { id: 'coordinator', label: 'Program Coordinator (PC)' },
                    { id: 'gad', label: 'Gender & Development (GAD)' },
                    { id: 'itso', label: 'Innovation & IP (ITSO)' },
                  ].map((spec) => {
                    const isChecked = (formData.evaluator_permissions || []).includes(spec.id);
                    return (
                      <label
                        key={spec.id}
                        className="flex items-center gap-2 rounded-xs border border-border bg-surface-subtle p-2.5 hover:border-primary/50 cursor-pointer select-none"
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) => {
                            const cur = formData.evaluator_permissions || [];
                            const next = e.target.checked
                              ? [...cur, spec.id]
                              : cur.filter((x) => x !== spec.id);
                            setFormData((prev) => ({ ...prev, evaluator_permissions: next }));
                          }}
                          className="accent-primary"
                        />
                        <span className="font-semibold text-text text-[11px]">{spec.label}</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            )}

            {updateUser.isError ? (
              <div className="rounded-sm border border-destructive/30 bg-destructive-soft px-4 py-3 text-sm text-destructive font-semibold">
                Failed to update user. Please try again.
              </div>
            ) : null}

            <div className="mt-6 flex items-center justify-end gap-3 pt-4 border-t border-border">
              <Button
                type="button"
                variant="secondary"
                onClick={handleClose}
                disabled={updateUser.isPending}
                className="text-xs font-semibold uppercase tracking-wider"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                isLoading={updateUser.isPending}
                className="text-xs font-semibold uppercase tracking-wider"
              >
                Save Changes
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
