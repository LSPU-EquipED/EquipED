export interface PreferenceLogItem {
  log_id: string;
  evaluation_id: string;
  user_id: string;
  action: string;
  edited_json: Record<string, unknown> | null;
  notes: string | null;
  created_at: string;
}

export interface PreferenceLogListResponse {
  items: PreferenceLogItem[];
  total: number;
  page: number;
  page_size: number;
}
