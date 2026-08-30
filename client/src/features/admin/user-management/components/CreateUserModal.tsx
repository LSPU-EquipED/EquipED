import { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/components/utils';
import { INPUT_STYLES } from '@/shared/constants/theme';
import { useCreateUser } from '../hooks/useAdminUsers';
import type { AdminUserCreateBody } from '../types';

interface CreateUserModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CreateUserModal({ open, onOpenChange }: CreateUserModalProps) {
  const createUser = useCreateUser();
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState<AdminUserCreateBody>({
    name: '',
    email: '',
    password: '',
    role: 'faculty',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = (): boolean => {
    const nextErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      nextErrors.name = 'Name is required.';
    }

    if (!formData.email.trim()) {
      nextErrors.email = 'Email is required.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      nextErrors.email = 'Invalid email format.';
    }

    if (!formData.password) {
      nextErrors.password = 'Password is required.';
    } else if (formData.password.length < 8) {
      nextErrors.password = 'Password must be at least 8 characters.';
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!validate()) return;

    try {
      await createUser.mutateAsync(formData);
      setFormData({ name: '', email: '', password: '', role: 'faculty' });
      onOpenChange(false);
    } catch {
      // Error is handled by the mutation
    }
  };

  const handleClose = () => {
    if (createUser.isPending) return;
    setFormData({ name: '', email: '', password: '', role: 'faculty' });
    setErrors({});
    onOpenChange(false);
  };

  if (!open) return null;

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
              Create Account
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
            Add a new user to the system. Faculty can upload SLMs and run evaluations. Admins can
            manage users, prompts, and review system activity.
          </p>

          <form onSubmit={handleSubmit} className="mt-6 grid gap-5">
            <div className="space-y-2">
              <label
                htmlFor="user-name"
                className="text-xs font-semibold uppercase tracking-wider text-text-muted"
              >
                Full Name
              </label>
              <input
                id="user-name"
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
                htmlFor="user-email"
                className="text-xs font-semibold uppercase tracking-wider text-text-muted"
              >
                Email
              </label>
              <input
                id="user-email"
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

            <div className="space-y-2">
              <label
                htmlFor="user-password"
                className="text-xs font-semibold uppercase tracking-wider text-text-muted"
              >
                Password
              </label>
              <div className="relative">
                <input
                  id="user-password"
                  type={showPassword ? 'text' : 'password'}
                  value={formData.password}
                  onChange={(e) => setFormData((prev) => ({ ...prev, password: e.target.value }))}
                  placeholder="At least 8 characters"
                  className={cn(
                    INPUT_STYLES.base,
                    'pl-3 pr-10 font-medium text-text placeholder:text-text-muted',
                    errors.password && 'border-destructive focus-visible:ring-destructive',
                  )}
                  aria-invalid={!!errors.password}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text cursor-pointer"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
              {errors.password ? (
                <p className="text-xs font-semibold text-destructive">{errors.password}</p>
              ) : null}
            </div>

            <div className="space-y-2">
              <label
                htmlFor="user-role"
                className="text-xs font-semibold uppercase tracking-wider text-text-muted"
              >
                Role
              </label>
              <select
                id="user-role"
                value={formData.role}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, role: e.target.value as 'admin' | 'faculty' }))
                }
                className="w-full h-10 border border-input bg-surface px-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm text-sm font-medium text-text cursor-pointer"
              >
                <option value="faculty">Faculty</option>
                <option value="admin">Admin</option>
              </select>
            </div>

            {createUser.isError ? (
              <div className="rounded-sm border border-destructive/30 bg-destructive-soft px-4 py-3 text-sm text-destructive font-semibold">
                Failed to create user. Please try again.
              </div>
            ) : null}

            <div className="mt-6 flex items-center justify-end gap-3 pt-4 border-t border-border">
              <Button
                type="button"
                variant="secondary"
                onClick={handleClose}
                disabled={createUser.isPending}
                className="text-xs font-semibold uppercase tracking-wider"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                isLoading={createUser.isPending}
                className="text-xs font-semibold uppercase tracking-wider"
              >
                Create Account
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
