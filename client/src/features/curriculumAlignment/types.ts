export interface Course {
  course_id: string;
  course_code: string;
  course_title: string;
  program: string;
}

export interface CourseListResponse {
  items: Course[];
}

export type AlignmentStatus = 'match' | 'under-developed' | 'over-developed' | 'not_addressed';

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
