import { BASE, getSessionId, throwApiError } from "./client";
import type { DefaultPrompts, PipelineConfigData, RuntimeInfo } from "./types";

export async function fetchRuntimeInfo(): Promise<RuntimeInfo> {
  const res = await fetch(`${BASE}/runtime_info`);
  if (!res.ok) await throwApiError(res, "Ошибка загрузки runtime info");
  return res.json() as Promise<RuntimeInfo>;
}

export async function fetchDefaultPrompts(): Promise<DefaultPrompts> {
  const res = await fetch(`${BASE}/default_prompts`);
  if (!res.ok) await throwApiError(res, "Ошибка загрузки промптов");
  return res.json() as Promise<DefaultPrompts>;
}

export async function getConfig(): Promise<PipelineConfigData | null> {
  const res = await fetch(`${BASE}/config`, { headers: { "X-Session-ID": getSessionId() } });
  if (!res.ok) await throwApiError(res, "Ошибка загрузки конфигурации");
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
    await throwApiError(res, "Ошибка сохранения конфигурации");
  }
}
