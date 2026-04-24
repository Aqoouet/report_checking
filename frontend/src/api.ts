const BASE = import.meta.env.VITE_API_URL ?? "/api";

function getSessionId(): string {
  let id = localStorage.getItem("rc_session_id");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("rc_session_id", id);
  }
  return id;
}

export interface CheckResponse {
  job_id: string;
}

export interface StatusResponse {
  status: "pending" | "processing" | "done" | "error" | "cancelled";
  current_checkpoint: number;
  total_checkpoints: number;
  current_checkpoint_name: string;
  current_checkpoint_short_name?: string;
  checkpoint_sub_current?: number;
  checkpoint_sub_total?: number;
  checkpoint_sub_location?: string;
  checkpoint_sub_name?: string;
  previous_result?: string;
  error: string | null;
}

export interface RuntimeInfo {
  check_model: string;
  context_tokens: number | null;
  doc_chunk_tokens: number;
  max_chunk_tokens: number;
  os: string;
}

export async function fetchRuntimeInfo(): Promise<RuntimeInfo> {
  const res = await fetch(`${BASE}/runtime_info`);
  if (!res.ok) throw new Error(`runtime_info ${res.status}`);
  return res.json() as Promise<RuntimeInfo>;
}

export interface ValidatePathResponse {
  valid: boolean;
  message: string;
  mapped_path: string;
}

export async function validatePath(filePath: string): Promise<ValidatePathResponse> {
  const form = new FormData();
  form.append("file_path", filePath);
  const res = await fetch(`${BASE}/validate_path`, { method: "POST", body: form });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? `Ошибка проверки пути: ${res.status}`);
  }
  return res.json() as Promise<ValidatePathResponse>;
}

export interface ValidateRangeResponse {
  valid: boolean;
  type: "sections" | "";
  items: Array<{ start: string; end: string }>;
  display: string;
  suggestion: string;
  server_error?: boolean;
  range_message?: string;
}

export async function validateRange(rangeText: string): Promise<ValidateRangeResponse> {
  const form = new FormData();
  form.append("range_text", rangeText);
  const res = await fetch(`${BASE}/validate_range`, { method: "POST", body: form });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? `Ошибка валидации: ${res.status}`);
  }
  return res.json();
}

export async function validateRangeQuick(rangeText: string): Promise<ValidateRangeResponse> {
  const form = new FormData();
  form.append("range_text", rangeText);
  const res = await fetch(`${BASE}/validate_range_quick`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`Ошибка быстрой валидации: ${res.status}`);
  return res.json();
}

export async function fetchDefaultCheckPrompt(): Promise<string> {
  const res = await fetch(`${BASE}/default_check_prompt`);
  if (!res.ok) throw new Error(`Ошибка загрузки промпта: ${res.status}`);
  const data = (await res.json()) as { prompt?: string };
  return data.prompt ?? "";
}

export interface DefaultPrompts {
  check_prompt: string;
  validation_prompt: string;
  summary_prompt: string;
}

export async function fetchDefaultPrompts(): Promise<DefaultPrompts> {
  const res = await fetch(`${BASE}/default_prompts`);
  if (!res.ok) throw new Error(`Ошибка загрузки промптов: ${res.status}`);
  return res.json() as Promise<DefaultPrompts>;
}

export async function startCheck(
  filePath: string,
  rangeSpec?: ValidateRangeResponse,
  checkPrompt?: string,
  temperature?: number,
): Promise<CheckResponse> {
  const form = new FormData();
  form.append("file_path", filePath);
  if (rangeSpec && rangeSpec.valid && rangeSpec.items.length > 0) {
    form.append("range_spec", JSON.stringify(rangeSpec));
  }
  form.append("check_prompt", checkPrompt ?? "");
  if (temperature !== undefined) {
    form.append("temperature", String(temperature));
  }
  const res = await fetch(`${BASE}/check`, { method: "POST", body: form });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? `Ошибка запуска проверки: ${res.status}`);
  }
  return res.json();
}

export async function pollStatus(jobId: string): Promise<StatusResponse> {
  const res = await fetch(`${BASE}/status/${jobId}`);
  if (!res.ok) throw new Error(`Ошибка статуса: ${res.status}`);
  return res.json();
}

export async function cancelJob(jobId: string): Promise<void> {
  const res = await fetch(`${BASE}/cancel/${jobId}`, { method: "POST" });
  if (!res.ok) throw new Error(`Ошибка отмены: ${res.status}`);
}

export function resultUrl(jobId: string): string {
  return `${BASE}/result/${jobId}`;
}

export function resultMdUrl(jobId: string): string {
  return `${BASE}/result_md/${jobId}`;
}

export function resultLogUrl(jobId: string): string {
  return `${BASE}/result_log/${jobId}`;
}

export async function fetchLog(jobId: string): Promise<string> {
  const res = await fetch(`${BASE}/result_log/${jobId}`);
  if (!res.ok) return "";
  const data = (await res.json()) as { log?: string };
  return data.log ?? "";
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

export async function getConfig(): Promise<PipelineConfigData | null> {
  const res = await fetch(`${BASE}/config`, { headers: { "X-Session-ID": getSessionId() } });
  if (!res.ok) throw new Error(`config ${res.status}`);
  const data = (await res.json()) as Record<string, unknown>;
  if (!data || Object.keys(data).length === 0) return null;
  return data as unknown as PipelineConfigData;
}

export async function postConfig(data: Partial<PipelineConfigData>): Promise<void> {
  const res = await fetch(`${BASE}/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Session-ID": getSessionId() },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({})) as { detail?: string };
    throw new Error(d.detail ?? `Ошибка сохранения конфигурации: ${res.status}`);
  }
}

export async function startCheckNew(): Promise<{ job_id: string; queue_position: number }> {
  const res = await fetch(`${BASE}/check`, { method: "POST", headers: { "X-Session-ID": getSessionId() } });
  if (!res.ok) {
    const d = await res.json().catch(() => ({})) as { detail?: string };
    throw new Error(d.detail ?? `Ошибка запуска проверки: ${res.status}`);
  }
  return res.json() as Promise<{ job_id: string; queue_position: number }>;
}

export async function fetchJobs(): Promise<JobSummary[]> {
  const res = await fetch(`${BASE}/jobs`);
  if (!res.ok) throw new Error(`jobs ${res.status}`);
  return res.json() as Promise<JobSummary[]>;
}
