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
  error: string | null;
}

export async function startCheck(filePath: string): Promise<CheckResponse> {
  const form = new FormData();
  form.append("file_path", filePath);

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
