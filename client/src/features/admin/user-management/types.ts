export interface AdminUserResponse {
  user_id: string;
  name: string;
  email: string;
  role: 'admin' | 'faculty';
  is_active: boolean;
  account_status: 'pending' | 'approved' | 'rejected' | 'suspended';
  faculty_id?: string | null;
  department?: string | null;
  program?: string | null;
  approved_at?: string | null;
  reviewed_at?: string | null;
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
  account_status?: AdminUserResponse['account_status'];
}
