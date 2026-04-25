import { ApiError, BASE, getSessionId, throwApiError } from "./client";
import type { JobSummary } from "./types";

export async function startCheckNew(): Promise<{ job_id: string; queue_position: number }> {
  const res = await fetch(`${BASE}/check`, { method: "POST", headers: { "X-Session-ID": getSessionId() } });
  if (!res.ok) {
    await throwApiError(res, "Ошибка запуска проверки");
  }
  return res.json() as Promise<{ job_id: string; queue_position: number }>;
}

export async function fetchJobs(): Promise<JobSummary[]> {
  const res = await fetch(`${BASE}/jobs`);
  if (!res.ok) await throwApiError(res, "Ошибка загрузки задач");
  return res.json() as Promise<JobSummary[]>;
}

export async function cancelJob(jobId: string): Promise<void> {
  const res = await fetch(`${BASE}/cancel/${jobId}`, { method: "POST" });
  if (!res.ok) await throwApiError(res, "Ошибка отмены");
}

export async function fetchLog(jobId: string): Promise<string> {
  const res = await fetch(`${BASE}/result_log/${jobId}`);
  if (!res.ok) {
    try {
      await throwApiError(res, "Ошибка загрузки лога");
    } catch (error) {
      if (error instanceof ApiError && error.code === "ERR_LOG_NOT_FOUND") {
        return "";
      }
      throw error;
    }
  }
  const data = (await res.json()) as { log?: string };
  return data.log ?? "";
}

export async function openArtifactDir(jobId: string): Promise<void> {
  const res = await fetch(`${BASE}/open_artifact/${jobId}`, { method: "POST" });
  if (!res.ok) await throwApiError(res, "Ошибка открытия папки");
}
