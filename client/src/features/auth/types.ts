export type UserRole = 'faculty' | 'sme' | 'coordinator' | 'gad' | 'itso' | 'admin';

export type AppAuthUser = {
  id: string;
  displayName: string;
  role: UserRole;
};

export type AppAuthContext = {
  status: 'anonymous' | 'authenticated';
  source: 'provisional';
  ready: boolean;
  user: AppAuthUser | null;
};
