export type ReadinessTier = 'empty' | 'single-evaluation' | 'small' | 'reasonable';

export interface ReadinessSummary {
  tier: ReadinessTier;
  message: string;
}

export interface TrainingTablePaginationControls {
  page: number;
  pageSize: number;
  totalPages: number;
  totalRecords: number;
  showPagination: boolean;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

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
  run_stage?: string | null;
  run_step?: number | null;
  run_total?: number | null;
  run_message?: string | null;
  run_reported_at?: string | null;
  seconds_since_report?: number | null;
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
  notebook?: string | null;
  notebook_filename?: string | null;
}

export interface TrainingSnapshot {
  step?: number | null;
  loss?: number | null;
  margin?: number | null;
  accuracy?: number | null;
  chosen?: number | null;
  rejected?: number | null;
}

export interface HeldoutSummary {
  pair_count?: number | null;
  loss?: number | null;
  margin?: number | null;
  accuracy?: number | null;
}

export interface TrainingSummary {
  version: number;
  steps?: number | null;
  epochs?: number | null;
  first?: TrainingSnapshot | null;
  last?: TrainingSnapshot | null;
  heldout?: HeldoutSummary | null;
}

export interface AdapterGgufInfo {
  size_bytes: number;
  sha256: string;
  uploaded_at: string;
}

export interface GgufDownloadLink {
  url: string;
  filename: string;
  sha256: string;
  size_bytes: number;
  expires_at: string;
}

export interface TrainedAdapterItem {
  adapter_id: string;
  agent_id: string;
  job_id: string;
  version: number;
  file_sha256: string;
  size_bytes: number;
  created_at: string;
  gguf_filename: string;
  loaded: boolean | null;
  published: boolean;
  training_summary?: TrainingSummary | null;
  gguf?: AdapterGgufInfo | null;
}

export interface TrainedAdapterListResponse {
  agent_id: string;
  adapters: TrainedAdapterItem[];
  published_adapter_id: string | null;
  server_reachable: boolean;
  unrecognized_server_adapters: string[];
}
