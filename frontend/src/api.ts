// In Docker: nginx proxies /api/* → backend:8000, so we use /api as base.
// In dev (npm run dev): set VITE_API_URL=http://localhost:8000 in frontend/.env
const BASE = import.meta.env.VITE_API_URL ?? "/api";

export interface UploadResponse {
  job_id: string;
}

export interface StatusResponse {
  status: "pending" | "processing" | "done" | "error";
  current_page: number;
  total_pages: number;
  error: string | null;
}

export async function uploadPdf(file: File, pages: string): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("pages", pages);

  const res = await fetch(`${BASE}/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? `Ошибка загрузки: ${res.status}`);
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
