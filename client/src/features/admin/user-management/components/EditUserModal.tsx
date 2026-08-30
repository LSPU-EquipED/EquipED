import { useState } from 'react';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/components/utils';
import { INPUT_STYLES } from '@/shared/constants/theme';
import { useUpdateUser } from '../hooks/useAdminUsers';
import type { AdminUserResponse, AdminUserUpdateBody } from '../types';

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
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = (): boolean => {
    const nextErrors: Record<string, string> = {};

    if (!formData.name?.trim()) {
      nextErrors.name = 'Name is required.';
    }

    if (!formData.email?.trim()) {
      nextErrors.email = 'Email is required.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      nextErrors.email = 'Invalid email format.';
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!user) return;
    if (!validate()) return;

    try {
      await updateUser.mutateAsync({ userId: user.user_id, body: formData });
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
            <h3 className="text-base font-bold uppercase tracking-wider text-text">
              Edit Account
            </h3>
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
                value={formData.email}
                onChange={(e) => setFormData((prev) => ({ ...prev, email: e.target.value }))}
                placeholder="juan@lspu.edu.ph"
                className={cn(
                  INPUT_STYLES.base,
                  'font-medium text-text placeholder:text-text-muted',
                  errors.email && 'border-destructive focus-visible:ring-destructive',
                )}
                aria-invalid={!!errors.email}
              />
              {errors.email ? (
                <p className="text-xs font-semibold text-destructive">{errors.email}</p>
              ) : null}
            </div>

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
