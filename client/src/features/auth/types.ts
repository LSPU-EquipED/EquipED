export type UserRole = 'faculty' | 'admin';

export type AppAuthUser = {
  id: string;
  displayName: string;
  email: string;
  role: UserRole;
};

export type AuthCredentials = {
  email: string;
  password: string;
};

export type AuthStateResponse = {
  authenticated: boolean;
  user: AppAuthUser | null;
};

export type AppAuthContext = {
  status: 'anonymous' | 'authenticated';
  source: 'provisional' | 'server';
  ready: boolean;
  error: string | null;
  user: AppAuthUser | null;
  login: (credentials: AuthCredentials) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  clearError: () => void;
};
