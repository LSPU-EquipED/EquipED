export interface Course {
  course_id: string;
  course_code: string;
  course_title: string;
  program: string;
}

export interface CourseListResponse {
  items: Course[];
}

export type AlignmentStatus = 'match' | 'under-developed' | 'over-developed' | 'not_addressed' | 'not_observed';

export type AlignmentCoverageScope = 'full' | 'bounded' | 'legacy_unknown';

export interface AlignmentCoverage {
  scope: AlignmentCoverageScope;
  total_pages: number | null;
  evaluated_pages: number | null;
  total_chars: number | null;
  evaluated_chars: number | null;
  strategy?: string | null;
}

export interface AlignmentFailure {
  kind?: string | null;
  detail?: string | null;
  classification?: string | null;
}

export interface AlignmentProvenance {
  coverage?: AlignmentCoverage | null;
  failure_kind?: string | null;
  failure?: AlignmentFailure | null;
  error_kind?: string | null;
  text_source?: string | null;
}

export interface ObjectiveResult {
  code: string;
  description: string;
  expected_level: 'I' | 'E' | 'D';
  is_addressed: boolean;
  observed_level: 'I' | 'E' | 'D' | null;
  status: AlignmentStatus;
  evidence: string | null;
  evidence_page: number | null;
}

export interface AlignmentCheckSummary {
  total_mapped_objectives: number;
  match: number;
  under_developed: number;
  over_developed: number;
  not_addressed: number;
  not_observed?: number;
}

export interface AlignmentCheck {
  check_id: string;
  document_id: string;
  course_id: string;
  course_title: string;
  run_at: string;
  model_name: string | null;
  objective_results: ObjectiveResult[];
  summary: AlignmentCheckSummary;
  success: boolean;
  error_message: string | null;
  provenance?: AlignmentProvenance | null;
  coverage?: AlignmentCoverage | null;
}

export interface DocumentPage {
  page_number: number;
  text: string;
}

export interface DocumentPagesResponse {
  pages: DocumentPage[];
}

export interface AlignmentCheckListItem {
  check_id: string;
  document_id: string;
  document_title: string;
  course_id: string;
  course_title: string;
  run_at: string;
  success: boolean;
  error_message: string | null;
  summary: AlignmentCheckSummary;
}

export interface AlignmentCheckListResponse {
  items: AlignmentCheckListItem[];
  total: number;
  page: number;
  page_size: number;
}
