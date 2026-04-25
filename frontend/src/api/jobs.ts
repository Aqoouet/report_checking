import { BASE, getSessionId } from "./client";
import type { JobSummary } from "./types";

export async function startCheckNew(): Promise<{ job_id: string; queue_position: number }> {
  const res = await fetch(`${BASE}/check`, { method: "POST", headers: { "X-Session-ID": getSessionId() } });
  if (!res.ok) {
    const d = await res.json().catch(() => ({})) as { detail?: string | { code: string; message: string } };
    const msg = typeof d.detail === "object" && d.detail !== null ? d.detail.message : d.detail;
    throw new Error(msg ?? `Ошибка запуска проверки: ${res.status}`);
  }
  return res.json() as Promise<{ job_id: string; queue_position: number }>;
}

export async function fetchJobs(): Promise<JobSummary[]> {
  const res = await fetch(`${BASE}/jobs`);
  if (!res.ok) throw new Error(`jobs ${res.status}`);
  return res.json() as Promise<JobSummary[]>;
}

export async function cancelJob(jobId: string): Promise<void> {
  const res = await fetch(`${BASE}/cancel/${jobId}`, { method: "POST" });
  if (!res.ok) throw new Error(`Ошибка отмены: ${res.status}`);
}

export async function fetchLog(jobId: string): Promise<string> {
  const res = await fetch(`${BASE}/result_log/${jobId}`);
  if (!res.ok) return "";
  const data = (await res.json()) as { log?: string };
  return data.log ?? "";
}
