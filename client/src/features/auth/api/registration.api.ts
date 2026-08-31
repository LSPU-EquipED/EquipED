import { requestJson } from '@/shared/api/http';

export type RegistrationBody = { name: string; email: string; password: string; faculty_id: string; department: string; program: string };
export type RegistrationStarted = { registration_token: string; email: string; message: string };

export const registrationApi = {
  start: (body: RegistrationBody) => requestJson<RegistrationStarted>('/auth/registrations', { method: 'POST', body: JSON.stringify(body) }),
  verify: (token: string, otp: string) => requestJson<{ status: string; message: string }>(`/auth/registrations/${token}/verify`, { method: 'POST', body: JSON.stringify({ otp }) }),
  resend: (token: string) => requestJson<RegistrationStarted>(`/auth/registrations/${token}/resend-otp`, { method: 'POST' }),
};
