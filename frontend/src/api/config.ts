import { BASE, getSessionId } from "./client";
import type { DefaultPrompts, PipelineConfigData, RuntimeInfo } from "./types";

export async function fetchRuntimeInfo(): Promise<RuntimeInfo> {
  const res = await fetch(`${BASE}/runtime_info`);
  if (!res.ok) throw new Error(`runtime_info ${res.status}`);
  return res.json() as Promise<RuntimeInfo>;
}

export async function fetchDefaultPrompts(): Promise<DefaultPrompts> {
  const res = await fetch(`${BASE}/default_prompts`);
  if (!res.ok) throw new Error(`Ошибка загрузки промптов: ${res.status}`);
  return res.json() as Promise<DefaultPrompts>;
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
