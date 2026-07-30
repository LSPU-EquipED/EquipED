export interface AdminUserResponse {
  user_id: string;
  name: string;
  email: string;
  role: 'admin' | 'faculty';
  is_active: boolean;
  created_at: string;
}

export interface AdminUserListResponse {
  items: AdminUserResponse[];
  total: number;
}

export interface AdminUserCreateBody {
  name: string;
  email: string;
  password: string;
  role: 'admin' | 'faculty';
}

export interface AdminUserUpdateBody {
  name?: string;
  email?: string;
  is_active?: boolean;
}
