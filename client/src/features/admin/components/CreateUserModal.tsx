import { useState } from 'react';
import { Loader2, Eye, EyeOff } from 'lucide-react';
import { useCreateUser } from '@/features/admin/hooks/useAdminUsers';
import type { AdminUserCreateBody } from '@/features/admin/types';

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
      className="fixed inset-0 z-50 flex justify-end bg-slate-900/40 backdrop-blur-xs animate-in fade-in"
      onClick={handleClose}
    >
      <div
        className="w-full sm:max-w-md bg-white border-l border-slate-200 p-6 sm:p-8 h-full flex flex-col justify-between overflow-y-auto animate-in slide-in-from-right relative"
        onClick={(e) => e.stopPropagation()}
      >
        <div>
          <div className="flex items-center justify-between pb-4 border-b border-slate-200">
            <h3 className="text-base font-bold uppercase tracking-wider text-slate-900">Create Account</h3>
            <button
              type="button"
              onClick={handleClose}
              className="text-slate-400 hover:text-slate-600 text-sm font-semibold uppercase tracking-wider focus:outline-none"
            >
              Close
            </button>
          </div>
          <p className="text-xs text-slate-500 font-semibold mt-3 leading-relaxed uppercase tracking-wider">
            Add a new user to the system. Faculty can upload SLMs and run evaluations. Admins can
            manage users, prompts, and review system activity.
          </p>

          <form onSubmit={handleSubmit} className="mt-6 grid gap-5">
            <div className="space-y-2">
              <label htmlFor="user-name" className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Full Name
              </label>
              <input
                id="user-name"
                value={formData.name}
                onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
                placeholder="Juan Dela Cruz"
                className="w-full h-10 px-3 border border-slate-200 bg-white rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[#1b3b87] placeholder:text-slate-400 font-semibold text-slate-800"
                aria-invalid={!!errors.name}
              />
              {errors.name ? <p className="text-xs font-semibold text-red-700">{errors.name}</p> : null}
            </div>

            <div className="space-y-2">
              <label htmlFor="user-email" className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Email
              </label>
              <input
                id="user-email"
                type="email"
                value={formData.email}
                onChange={(e) => setFormData((prev) => ({ ...prev, email: e.target.value }))}
                placeholder="juan@lspu.edu.ph"
                className="w-full h-10 px-3 border border-slate-200 bg-white rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[#1b3b87] placeholder:text-slate-400 font-semibold text-slate-800"
                aria-invalid={!!errors.email}
              />
              {errors.email ? <p className="text-xs font-semibold text-red-700">{errors.email}</p> : null}
            </div>

            <div className="space-y-2">
              <label htmlFor="user-password" className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Password
              </label>
              <div className="relative">
                <input
                  id="user-password"
                  type={showPassword ? 'text' : 'password'}
                  value={formData.password}
                  onChange={(e) => setFormData((prev) => ({ ...prev, password: e.target.value }))}
                  placeholder="At least 8 characters"
                  className="w-full h-10 pl-3 pr-10 border border-slate-200 bg-white rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[#1b3b87] placeholder:text-slate-400 font-semibold text-slate-805"
                  aria-invalid={!!errors.password}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
              {errors.password ? <p className="text-xs font-semibold text-red-700">{errors.password}</p> : null}
            </div>

            <div className="space-y-2">
              <label htmlFor="user-role" className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Role
              </label>
              <select
                id="user-role"
                value={formData.role}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, role: e.target.value as 'admin' | 'faculty' }))
                }
                className="w-full h-10 border border-slate-200 bg-white px-3 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] rounded-sm text-sm font-semibold text-slate-850 cursor-pointer"
              >
                <option value="faculty">Faculty</option>
                <option value="admin">Admin</option>
              </select>
            </div>

            {createUser.isError ? (
              <div className="rounded-sm border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 font-semibold">
                Failed to create user. Please try again.
              </div>
            ) : null}

            <div className="mt-6 flex items-center justify-end gap-3 pt-4 border-t border-slate-200">
              <button
                type="button"
                onClick={handleClose}
                disabled={createUser.isPending}
                className="inline-flex h-10 items-center justify-center border border-slate-200 hover:bg-slate-50 text-slate-700 px-4 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-slate-200 focus:outline-none disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={createUser.isPending}
                className="inline-flex h-10 items-center justify-center bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-white px-4 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87] focus:outline-none disabled:opacity-50"
              >
                {createUser.isPending ? (
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="size-4 animate-spin" />
                    Creating...
                  </span>
                ) : (
                  'Create Account'
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
