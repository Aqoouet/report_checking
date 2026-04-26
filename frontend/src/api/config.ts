import { BASE, getSessionId, throwApiError } from "./client";
import type {
  ConfigDefaults,
  DefaultPrompts,
  OutputDirValidationResult,
  PathValidationResult,
  PipelineConfigData,
  RangeValidationResult,
  RuntimeInfo,
} from "./types";

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

export async function fetchConfigDefaults(): Promise<ConfigDefaults> {
  const res = await fetch(`${BASE}/config_defaults`);
  if (!res.ok) await throwApiError(res, "Ошибка загрузки значений по умолчанию");
  return res.json() as Promise<ConfigDefaults>;
}

export async function fetchFieldHelp(field: string): Promise<string> {
  const res = await fetch(`${BASE}/field_help/${encodeURIComponent(field)}`);
  if (!res.ok) await throwApiError(res, "Ошибка загрузки справки");
  return res.text();
}

export async function getConfig(): Promise<PipelineConfigData | null> {
  const res = await fetch(`${BASE}/config`, { headers: { "X-Session-ID": getSessionId() } });
  if (!res.ok) await throwApiError(res, "Ошибка загрузки конфигурации");
  const data = (await res.json()) as Record<string, unknown>;
  if (!data || Object.keys(data).length === 0) return null;
  return data as unknown as PipelineConfigData;
}

export async function postConfig(data: Partial<PipelineConfigData> & { _original_yaml?: string }): Promise<void> {
  const res = await fetch(`${BASE}/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Session-ID": getSessionId() },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    await throwApiError(res, "Ошибка сохранения конфигурации");
  }
}

export async function validateInputPath(filePath: string): Promise<PathValidationResult> {
  const body = new FormData();
  body.append("file_path", filePath);
  const res = await fetch(`${BASE}/validate_path`, {
    method: "POST",
    body,
  });
  if (!res.ok) await throwApiError(res, "Ошибка проверки пути к файлу");
  return res.json() as Promise<PathValidationResult>;
}

export async function validateOutputDirPath(outputDir: string): Promise<OutputDirValidationResult> {
  const body = new FormData();
  body.append("output_dir", outputDir);
  const res = await fetch(`${BASE}/validate_output_dir`, {
    method: "POST",
    body,
  });
  if (!res.ok) await throwApiError(res, "Ошибка проверки папки результатов");
  return res.json() as Promise<OutputDirValidationResult>;
}

export async function validateSubchaptersRange(rangeText: string): Promise<RangeValidationResult> {
  const body = new FormData();
  body.append("range_text", rangeText);
  const res = await fetch(`${BASE}/validate_range`, {
    method: "POST",
    body,
  });
  if (!res.ok) await throwApiError(res, "Ошибка проверки диапазона");
  return res.json() as Promise<RangeValidationResult>;
}
