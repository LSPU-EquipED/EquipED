export interface PromptVersionItem {
  version_id: string;
  version_number: number;
  prompt_text: string;
  is_active: boolean;
  updated_by: string | null;
  motivation: string | null;
  created_at: string;
}

export interface PromptVersionListResponse {
  agent_id: string;
  versions: PromptVersionItem[];
  total: number;
}

export interface PromptCreateBody {
  prompt_text: string;
  motivation?: string;
}

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
