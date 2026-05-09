import { createContext, useContext } from 'react';
import type { AppAuthContext } from '../types';

export const AuthContext = createContext<AppAuthContext | null>(null);

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }

  return context;
}
