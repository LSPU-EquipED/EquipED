import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { useUpdateUser } from '@/features/admin/hooks/useAdminUsers';
import type { AdminUserResponse, AdminUserUpdateBody } from '@/features/admin/types';

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
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/40" onClick={handleClose}>
      <div
        className="w-full sm:max-w-md bg-white border-l border-slate-200 p-6 sm:p-8 h-full flex flex-col justify-between overflow-y-auto relative"
        onClick={(e) => e.stopPropagation()}
      >
        <div>
          <div className="flex items-center justify-between pb-4 border-b border-slate-200">
            <h3 className="text-base font-bold uppercase tracking-wider text-slate-900">
              Edit Account
            </h3>
            <button
              type="button"
              onClick={handleClose}
              className="text-slate-400 hover:text-slate-600 text-sm font-semibold uppercase tracking-wider focus:outline-none"
            >
              Close
            </button>
          </div>
          <p className="text-xs text-slate-500 font-semibold mt-3 leading-relaxed uppercase tracking-wider">
            Update the name and email for {user.name}. Changes apply immediately.
          </p>

          <form onSubmit={handleSubmit} className="mt-6 grid gap-5">
            <div className="space-y-2">
              <label
                htmlFor="edit-user-name"
                className="text-xs font-bold uppercase tracking-wider text-slate-500"
              >
                Full Name
              </label>
              <input
                id="edit-user-name"
                value={formData.name}
                onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
                placeholder="Juan Dela Cruz"
                className="w-full h-10 px-3 border border-slate-200 bg-white rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[#1b3b87] placeholder:text-slate-600 font-semibold text-slate-800"
                aria-invalid={!!errors.name}
              />
              {errors.name ? (
                <p className="text-xs font-semibold text-[#b91c1c]">{errors.name}</p>
              ) : null}
            </div>

            <div className="space-y-2">
              <label
                htmlFor="edit-user-email"
                className="text-xs font-bold uppercase tracking-wider text-slate-500"
              >
                Email
              </label>
              <input
                id="edit-user-email"
                type="email"
                value={formData.email}
                onChange={(e) => setFormData((prev) => ({ ...prev, email: e.target.value }))}
                placeholder="juan@lspu.edu.ph"
                className="w-full h-10 px-3 border border-slate-200 bg-white rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[#1b3b87] placeholder:text-slate-600 font-semibold text-slate-800"
                aria-invalid={!!errors.email}
              />
              {errors.email ? (
                <p className="text-xs font-semibold text-[#b91c1c]">{errors.email}</p>
              ) : null}
            </div>

            {updateUser.isError ? (
              <div className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 px-4 py-3 text-sm text-[#b91c1c] font-semibold">
                Failed to update user. Please try again.
              </div>
            ) : null}

            <div className="mt-6 flex items-center justify-end gap-3 pt-4 border-t border-slate-200">
              <button
                type="button"
                onClick={handleClose}
                disabled={updateUser.isPending}
                className="inline-flex h-10 items-center justify-center border border-slate-200 hover:bg-slate-50 text-slate-700 px-4 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87] focus:outline-none disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={updateUser.isPending}
                className="inline-flex h-10 items-center justify-center bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-white px-4 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87] focus:outline-none disabled:opacity-50"
              >
                {updateUser.isPending ? (
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="size-4 animate-spin" />
                    Saving...
                  </span>
                ) : (
                  'Save Changes'
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
