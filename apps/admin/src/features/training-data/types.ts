export interface TrainingJobItem {
  job_id: string;
  agent_id: string;
  status: 'pending' | 'downloaded' | 'completed';
  created_at: string;
  pair_count?: number | null;
  evaluation_count?: number | null;
  reviewer_count?: number | null;
  pairs_sha256?: string | null;
  export_timestamp?: string | null;
}

export interface DatasetReadiness {
  agent_id: string;
  pair_count: number;
  evaluation_count: number;
  reviewer_count: number;
  skipped_counts: Record<string, number>;
  pairs_sha256: string;
  export_timestamp: string;
}

export interface TrainingJobListResponse {
  agent_id: string;
  jobs: TrainingJobItem[];
}

export interface TrainingJobCreateResponse {
  job_id: string;
  agent_id: string;
  status: string;
  download_url: string;
  upload_url: string;
  download_expires_at: string;
  upload_expires_at: string;
  created_at: string;
}

export interface TrainedAdapterItem {
  adapter_id: string;
  agent_id: string;
  job_id: string;
  version: number;
  file_sha256: string;
  size_bytes: number;
  created_at: string;
}

export interface TrainedAdapterListResponse {
  agent_id: string;
  adapters: TrainedAdapterItem[];
}
