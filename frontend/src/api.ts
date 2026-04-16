const BASE = import.meta.env.VITE_API_URL ?? "/api";

export interface CheckResponse {
  job_id: string;
}

export interface StatusResponse {
  status: "pending" | "processing" | "done" | "error";
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

export interface ValidateRangeResponse {
  valid: boolean;
  type: "sections" | "pages" | "";
  items: Array<{ start: string; end: string }>;
  display: string;
  suggestion: string;
}

export async function validateRange(
  rangeText: string,
  fileType: string,
): Promise<ValidateRangeResponse> {
  const form = new FormData();
  form.append("range_text", rangeText);
  form.append("file_type", fileType);

  const res = await fetch(`${BASE}/validate_range`, { method: "POST", body: form });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? `Ошибка валидации: ${res.status}`);
  }
  return res.json();
}

export async function startCheck(
  filePath: string,
  rangeSpec?: ValidateRangeResponse,
): Promise<CheckResponse> {
  const form = new FormData();
  form.append("file_path", filePath);
  if (rangeSpec && rangeSpec.valid && rangeSpec.items.length > 0) {
    form.append("range_spec", JSON.stringify(rangeSpec));
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

export function resultUrl(jobId: string): string {
  return `${BASE}/result/${jobId}`;
}
