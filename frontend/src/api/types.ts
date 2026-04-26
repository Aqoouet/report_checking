export interface RuntimeInfo {
  check_model: string;
  context_tokens: number | null;
  doc_chunk_tokens: number;
  max_chunk_tokens: number;
  os: string;
}

export interface DefaultPrompts {
  check_prompt: string;
  validation_prompt: string;
  summary_prompt: string;
}

export interface ConfigDefaults {
  input_docx_path: string;
  output_dir: string;
  subchapters_range: string;
  chunk_size_tokens: number;
  temperature: number | null;
}

export interface PipelineConfigData {
  input_docx_path: string;
  output_dir: string;
  check_prompt: string;
  validation_prompt: string;
  summary_prompt: string;
  subchapters_range: string;
  chunk_size_tokens: number;
  temperature: number | null;
}

export interface PathValidationResult {
  valid: boolean;
  message: string;
  mapped_path: string;
  code?: string;
}

export interface OutputDirValidationResult {
  valid: boolean;
  message: string;
  resolved_path: string;
  code?: string;
}

export interface RangeValidationItem {
  start: string;
  end: string;
}

export interface RangeValidationResult {
  valid: boolean;
  type?: string;
  items?: RangeValidationItem[];
  display?: string;
  suggestion?: string;
  range_message?: string;
  server_error?: boolean;
}

export interface JobSummary {
  id: string;
  status: "pending" | "processing" | "done" | "error" | "cancelled";
  phase: string;
  docx_name: string;
  current_checkpoint_name: string;
  checkpoint_sub_current: number;
  checkpoint_sub_total: number;
  queue_position: number;
  submitted_at: number;
  finished_at: number | null;
  error: string | null;
  artifact_dir: string | null;
  artifact_dir_windows: string | null;
  artifact_dir_file_url: string | null;
  failed_sections_count: number;
}
