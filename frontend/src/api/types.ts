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
  artifact_dir: string;
}
